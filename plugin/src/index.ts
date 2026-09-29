// OpenClaw 插件：仅向 Agent 提供知识检索能力。
// query 为检索文本；knowledge_base_ids 可选，用于限定知识库；top_k 为返回条数上限。
type SearchInput = { query: string; knowledge_base_ids?: string[]; top_k?: number }
// 知识服务响应：包含命中片段、文档来源、所属知识库和相关性分数。
type SearchResult = {
    results?: Array<{
        content?: string; document_name?: string; document_id?: string;
        knowledge_base_id?: string; score?: number
    }>
}

// 插件入口：通过 OpenClaw 提供的 API 注册可供 Agent 调用的工具。
export default function register(api: any) {
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
}
