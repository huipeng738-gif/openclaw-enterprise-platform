// OpenClaw 插件：提供受控企业查询，并隔离数据库分析任务的 Tool 调用。
// query 为检索文本；knowledge_base_ids 可选，用于限定知识库；top_k 为返回条数上限。
type SearchInput = { query: string; knowledge_base_ids?: string[]; top_k?: number }
// 知识服务响应：包含命中片段、文档来源、所属知识库和相关性分数。
type SearchResult = {
    results?: Array<{
        content?: string; document_name?: string; document_id?: string;
        knowledge_base_id?: string; score?: number
    }>
}

type OrderInput = { order_no: string }
type CustomerInput = { customer_no: string }
type MetricInput = { metric: string; start_date: string; end_date: string; group_by?: 'day' | 'week' | 'month' }
type FollowupInput = { title: string; reason?: string; order_no?: string }
type CancelRequestInput = { target_task_id: string; reason: string }

// 只在 Gateway 提供平台任务 session 时向后端提交 Action；身份由宿主上下文确定。
async function submitAction(api: any, path: string, sessionKey: string, toolCallId: string,
                            input: FollowupInput | CancelRequestInput) {
    const token = process.env.PLUGIN_SERVICE_TOKEN
    const base = api.pluginConfig?.businessUrl
    if (!token || !base) throw new Error('Action service is not configured')
    const response = await fetch(`${String(base).replace(/\/$/, '')}${path}`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-Plugin-Token': token},
        body: JSON.stringify({...input, session_key: sessionKey, tool_call_id: toolCallId}),
        signal: AbortSignal.timeout(api.pluginConfig?.timeoutMs ?? 15000),
    })
    if (!response.ok) throw new Error(`Action request failed (${response.status})`)
    return {content: [{type: 'text', text: JSON.stringify(await response.json())}]}
}

// 以插件服务凭证调用 FastAPI 的确定性业务查询入口，超时和错误仅返回状态信息。
async function businessQuery(api: any, path: string, input: OrderInput | CustomerInput) {
    const token = process.env.PLUGIN_SERVICE_TOKEN
    const config = api.pluginConfig || {}
    if (!token || !config.businessUrl) throw new Error('Business query is not configured')
    const response = await fetch(`${String(config.businessUrl).replace(/\/$/, '')}${path}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Plugin-Token': token},
        body: JSON.stringify(input),
        signal: AbortSignal.timeout(config.timeoutMs ?? 15000),
    })
    if (!response.ok) throw new Error(`Business query failed (${response.status})`)
    return {content: [{type: 'text', text: JSON.stringify(await response.json())}]}
}

// 插件入口：通过 OpenClaw 提供的 API 注册可供 Agent 调用的工具。
export default function register(api: any) {
    // 数据库任务只让模型规划与解释；任意 Tool 调用在执行前由 Gateway 拒绝。
    api.on('before_tool_call', (_event: unknown, ctx: { sessionKey?: string }) => {
        if (typeof ctx.sessionKey === 'string' &&
            /^agent:coordinator:enterprise-db:[a-f0-9]{32}$/.test(ctx.sessionKey)) {
            return {block: true, blockReason: 'Database analysis session cannot call tools'}
        }
    })
    api.registerTool({
        name: 'knowledge_search',
        label: 'Knowledge Search',
        description: 'Search enterprise knowledge and return passages with verified document sources.',
        // 使用 JSON Schema 声明必填参数、长度和数量限制，并禁止额外字段。
        parameters: {
            type: 'object', additionalProperties: false, required: ['query'],
            properties: {
                query: {type: 'string', minLength: 1, maxLength: 1000},
                knowledge_base_ids: {type: 'array', maxItems: 20, items: {type: 'string'}},
                top_k: {type: 'integer', minimum: 1, maximum: 20},
            },
        },
        // _toolCallId 由运行时传入，当前检索请求不使用该调用标识。
        async execute(_toolCallId: string, input: SearchInput) {
            // 服务凭证从环境变量读取；服务地址和超时时间来自插件配置。
            const serviceToken = process.env.PLUGIN_SERVICE_TOKEN
            const config = api.pluginConfig || {}
            if (!serviceToken || !config.knowledgeUrl) throw new Error('Knowledge search is not configured')
            // 携带插件服务凭证调用知识检索接口，默认最多返回 5 条结果。
            const response = await fetch(config.knowledgeUrl, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-Plugin-Token': serviceToken},
                body: JSON.stringify({
                    query: input.query, knowledge_base_ids: input.knowledge_base_ids,
                    top_k: input.top_k ?? 5
                }),
                // 默认 15 秒超时，超时后中止请求。
                signal: AbortSignal.timeout(config.timeoutMs ?? 15000),
            })
            // 非成功 HTTP 状态直接抛错，由工具运行时处理调用失败。
            if (!response.ok) throw new Error(`Knowledge search failed (${response.status})`)
            const data = await response.json() as SearchResult
            // 为缺失字段补默认值，并保留来源标识；source 使用文档名称。
            const results = (data.results || []).map(item => ({
                content: item.content || '', source: item.document_name || '',
                document_name: item.document_name || '', document_id: item.document_id || '',
                knowledge_base_id: item.knowledge_base_id || '', score: item.score ?? 0,
            }))
            // 按工具文本内容格式返回 JSON；无命中时提醒 Agent 不要编造引用来源。
            return {
                content: [{
                    type: 'text', text: JSON.stringify({
                        results, message: results.length ? undefined : '没有匹配知识，请不要编造引用来源。',
                    })
                }]
            }
        },
    })

    api.registerTool({
        name: 'order_query',
        label: 'Order Query',
        description: 'Look up one enterprise order by its exact order number. Read-only and deterministic.',
        parameters: {
            type: 'object', additionalProperties: false, required: ['order_no'],
            properties: {order_no: {type: 'string', pattern: '^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$'}},
        },
        // 将受控订单编号交给 FastAPI，SQL 只由后端 Repository 固定生成。
        async execute(_toolCallId: string, input: OrderInput) {
            return businessQuery(api, '/business/orders/query', input)
        },
    })

    api.registerTool({
        name: 'customer_query',
        label: 'Customer Query',
        description: 'Look up one enterprise customer by exact customer number with a bounded order summary.',
        parameters: {
            type: 'object', additionalProperties: false, required: ['customer_no'],
            properties: {customer_no: {type: 'string', pattern: '^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$'}},
        },
        // 将受控客户编号交给 FastAPI，手机号由后端统一脱敏。
        async execute(_toolCallId: string, input: CustomerInput) {
            return businessQuery(api, '/business/customers/query', input)
        },
    })

    api.registerTool({
        name: 'metrics_query',
        label: 'Metrics Query',
        description: 'Query one code-defined enterprise metric over a bounded date range.',
        parameters: {
            type: 'object', additionalProperties: false,
            required: ['metric', 'start_date', 'end_date'],
            properties: {
                metric: {type: 'string', enum: ['sales_amount', 'order_count', 'refund_rate', 'active_customer_count']},
                start_date: {type: 'string', format: 'date'},
                end_date: {type: 'string', format: 'date'},
                group_by: {type: 'string', enum: ['day', 'week', 'month']},
            },
        },
        // 指标定义在后端注册表，插件仅提交受控选择与日期参数。
        async execute(_toolCallId: string, input: MetricInput) {
            const token = process.env.PLUGIN_SERVICE_TOKEN
            const config = api.pluginConfig || {}
            if (!token || !config.metricsUrl) throw new Error('Metrics query is not configured')
            const response = await fetch(config.metricsUrl, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-Plugin-Token': token},
                body: JSON.stringify(input),
                signal: AbortSignal.timeout(config.timeoutMs ?? 15000),
            })
            if (!response.ok) throw new Error(`Metrics query failed (${response.status})`)
            return {content: [{type: 'text', text: JSON.stringify(await response.json())}]}
        },
    })

    // 仅为平台发起的 Agent 任务创建动作工具；其他会话在工具发现阶段不可见。
    api.registerTool((ctx: { sessionKey?: string }) => {
            const sessionKey = ctx.sessionKey
            if (!sessionKey || !/^agent:[A-Za-z0-9_-]{1,48}:enterprise:[a-f0-9]{32}$/.test(sessionKey)) return null
            return {
                name: 'task_create', label: 'Create Follow-up Task',
                description: 'Create a follow-up work item for the current platform user. Does not launch another Agent run.',
                parameters: {type: 'object', additionalProperties: false, required: ['title'], properties: {
                    title: {type: 'string', minLength: 3, maxLength: 160},
                    reason: {type: 'string', maxLength: 500},
                    order_no: {type: 'string', pattern: '^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$'},
                }},
                execute(toolCallId: string, input: FollowupInput) {
                    return submitAction(api, '/actions/task-create', sessionKey, toolCallId, input)
                },
            }
    }, {name: 'task_create'})

    // 高风险任务取消只创建审批请求；真正取消由后端在批准事务中执行。
    api.registerTool((ctx: { sessionKey?: string }) => {
            const sessionKey = ctx.sessionKey
            if (!sessionKey || !/^agent:[A-Za-z0-9_-]{1,48}:enterprise:[a-f0-9]{32}$/.test(sessionKey)) return null
            return {
                name: 'task_cancel_request', label: 'Request Task Cancellation',
                description: 'Request administrator approval to cancel one task owned by the current platform user.',
                parameters: {type: 'object', additionalProperties: false,
                    required: ['target_task_id', 'reason'], properties: {
                        target_task_id: {type: 'string', pattern: '^[a-f0-9]{32}$'},
                        reason: {type: 'string', minLength: 3, maxLength: 500},
                    }},
                execute(toolCallId: string, input: CancelRequestInput) {
                    return submitAction(api, '/actions/task-cancel/request', sessionKey, toolCallId, input)
                },
            }
    }, {name: 'task_cancel_request'})
}
