
#  openclaw.plugin.json:这个插件是谁、有什么能力和配置
{
  /*
   * 插件基本信息：
   * id 是 OpenClaw 内部识别插件的唯一标识；
   * name 用于 CLI / UI 展示；version 是插件版本；
   * description 描述插件用途——为 OpenClaw 提供企业知识库和指标查询能力。
   */
  "id": "enterprise-data-tools",
  "name": "Enterprise Data Tools",
  "version": "1.0.0",
  "description": "Enterprise knowledge and metrics tools for OpenClaw",

  /*
   * 插件激活策略：
   * onStartup=true 表示 OpenClaw 启动时激活该插件。
   */
  "activation": {
    "onStartup": true
  },

  /*
   * Tool 能力声明：
   * 声明 enterprise-data-tools 提供 knowledge_search。
   * 这里只是声明 Tool，真正的实现仍然在 src/index.ts 中通过
   * api.registerTool(...) 完成。
   *
   * 对应关系：
   * contracts.tools → knowledge_search
   *                         ↓
   *                  src/index.ts
   *                         ↓
   *                api.registerTool(...)
   */
  "contracts": {
    "tools": [
      "knowledge_search"
    ]
  },

  /*
   * 插件配置 Schema：
   * knowledgeUrl：知识库查询接口，后续 knowledge_search Tool 调用该接口
   * metricsUrl：系统指标查询接口，目前只是配置项，并不代表已经注册 metrics Tool
   * timeoutMs：HTTP 请求超时时间，默认 15000ms（15 秒）
   *
   * additionalProperties=false 表示不允许配置 Schema 之外的其他字段。
   *
   * knowledge_search 调用链：
   * Agent → knowledge_search → Plugin → FastAPI :8100
   *       → /knowledge/search → RAGFlow → 返回检索结果 → Agent
   */
  "configSchema": {
    "type": "object",
    "properties": {
      "knowledgeUrl": {
        "type": "string",
        "default": "http://127.0.0.1:8100/knowledge/search"
      },
      "metricsUrl": {
        "type": "string",
        "default": "http://127.0.0.1:8100/metrics/query"
      },
      "timeoutMs": {
        "type": "integer",
        "default": 15000
      }
    },
    "additionalProperties": false
  }
}

#  

#  package.json:我的运行时代码在哪里
{
  /*
   * npm 包基本信息
   * name 是 Node/npm 包名；private=true 防止误发布到公共 npm；
   * type=module 表示使用 ESM，即 import/export 语法。
   */
  "name": "enterprise-data-tools",
  "version": "1.0.0",
  "private": true,
  "type": "module",

  /*
   * TypeScript 类型检查命令：
   * npm run typecheck → tsc --noEmit
   * 只检查 src/index.ts 等 TS 文件是否有类型错误，不生成 JS 文件。
   */
  "scripts": {
    "typecheck": "tsc --noEmit"
  },

  /*
   * OpenClaw 插件入口配置：
   * OpenClaw 发现这个 npm 包后，会读取 extensions，
   * 然后加载 ./src/index.ts，执行其中的插件注册逻辑。
   *
   * 调用关系：
   * OpenClaw → package.json → src/index.ts
   *          → register() → registerTool() → knowledge_search
   *
   * 这也是 openclaw plugins list 中 Source 显示 src/index.ts 的原因。
   */
  "openclaw": {
    "extensions": [
      "./src/index.ts"
    ]
  },

  /*
   * 开发依赖：
   * @types/node：提供 process、Buffer 等 Node.js API 的 TS 类型
   * typescript：提供 tsc 编译器，用于上面的 typecheck
   */
  "devDependencies": {
    "@types/node": "^24.19.0",
    "typescript": "~5.9.2"
  }
}