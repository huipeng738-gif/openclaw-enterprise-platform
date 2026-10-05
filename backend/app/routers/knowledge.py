"""User and OpenClaw-plugin entrypoints for the same knowledge service."""
from pathlib import PurePath

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from app.schemas.knowledge import DatasetCreate, ParseRequest, RagflowId, SearchRequest
from app.services.knowledge import KnowledgeService


MAX_UPLOAD_BYTES = 20 * 1024 * 1024


# 组装用户与插件共用的知识库路由，注入权限、审计及 Redis 提供器。
def build_knowledge_router(permission, plugin_guard, audit, redis_provider):
    router = APIRouter()

    # 从应用状态获取 RAGFlow 客户端并构建业务服务，未配置时返回 503。
    def service(request: Request):
        client = getattr(request.app.state, 'ragflow', None)
        if client is None:
            raise HTTPException(503, 'RAGFlow is not configured')
        return KnowledgeService(client, redis_provider())

    # 返回平台托管知识库列表。
    @router.get('/api/knowledge/bases')
    @router.get('/api/knowledge/datasets')
    async def datasets(user=Depends(permission('knowledge:read')), knowledge=Depends(service)):
        return await knowledge.list_datasets()

    # 仅管理员查看尚未关联到平台的 RAGFlow 知识库。
    @router.get('/api/knowledge/datasets/available')
    async def available_datasets(user=Depends(permission('knowledge:write')), knowledge=Depends(service)):
        return await knowledge.list_available_datasets()

    # 创建知识库并记录当前用户的操作审计。
    @router.post('/api/knowledge/bases', status_code=201)
    @router.post('/api/knowledge/datasets', status_code=201)
    async def create_dataset(body: DatasetCreate, user=Depends(permission('knowledge:write')),
                             knowledge=Depends(service)):
        created = await knowledge.create_dataset(body.name)
        await audit(user['username'], 'knowledge.create', created['id'])
        return created

    # 关联已有 RAGFlow 数据集并记录审计。
    @router.post('/api/knowledge/datasets/{dataset_id}/register')
    async def register_dataset(dataset_id: RagflowId, user=Depends(permission('knowledge:write')),
                               knowledge=Depends(service)):
        registered = await knowledge.register_dataset(dataset_id)
        await audit(user['username'], 'knowledge.dataset.register', dataset_id)
        return registered

    # 返回可访问知识库的详情。
    @router.get('/api/knowledge/bases/{dataset_id}')
    async def dataset_detail(dataset_id: RagflowId, user=Depends(permission('knowledge:read')),
                             knowledge=Depends(service)):
        return await knowledge.get_dataset(dataset_id)

    # 删除知识库并记录审计，成功时返回无内容响应。
    @router.delete('/api/knowledge/bases/{dataset_id}', status_code=204)
    async def delete_dataset(dataset_id: RagflowId, user=Depends(permission('knowledge:delete')),
                             knowledge=Depends(service)):
        await knowledge.delete_dataset(dataset_id)
        await audit(user['username'], 'knowledge.delete', dataset_id)

    # 按经过范围校验的分页参数读取知识库文档。
    @router.get('/api/knowledge/bases/{dataset_id}/documents')
    @router.get('/api/knowledge/datasets/{dataset_id}/documents')
    async def documents(dataset_id: RagflowId, page: int = Query(default=1, ge=1),
                        page_size: int = Query(default=30, ge=1, le=100),
                        user=Depends(permission('knowledge:read')), knowledge=Depends(service)):
        return await knowledge.list_documents(dataset_id, page, page_size)

    # 提取安全文件名并限制上传大小为 20 MB，上传成功后记录审计。
    @router.post('/api/knowledge/bases/{dataset_id}/documents', status_code=201)
    @router.post('/api/knowledge/datasets/{dataset_id}/documents', status_code=201)
    async def upload(dataset_id: RagflowId, file: UploadFile = File(...),
                     user=Depends(permission('knowledge:write')), knowledge=Depends(service)):
        filename = PurePath((file.filename or '').replace('\\', '/')).name
        if not filename or filename in {'.', '..'}:
            raise HTTPException(400, 'invalid filename')
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, 'document exceeds 20 MB')
        uploaded = await knowledge.upload_document(dataset_id, filename, content,
                                                   file.content_type or 'application/octet-stream')
        await audit(user['username'], 'document.upload', dataset_id)
        return uploaded

    # 删除指定知识库文档并记录审计。
    @router.delete('/api/knowledge/bases/{dataset_id}/documents/{document_id}', status_code=204)
    async def delete_document(dataset_id: RagflowId, document_id: RagflowId,
                              user=Depends(permission('knowledge:delete')), knowledge=Depends(service)):
        await knowledge.delete_document(dataset_id, document_id)
        await audit(user['username'], 'document.delete', document_id)

    # 读取文档信息与当前解析状态。
    @router.get('/api/knowledge/bases/{dataset_id}/documents/{document_id}/status')
    async def document_status(dataset_id: RagflowId, document_id: RagflowId,
                              user=Depends(permission('knowledge:read')), knowledge=Depends(service)):
        return await knowledge.get_document_status(dataset_id, document_id)

    # 受理批量文档解析请求并记录审计，不等待解析完成。
    @router.post('/api/knowledge/datasets/{dataset_id}/parse', status_code=202)
    async def parse(dataset_id: RagflowId, body: ParseRequest,
                    user=Depends(permission('knowledge:write')), knowledge=Depends(service)):
        await knowledge.parse_documents(dataset_id, body.document_ids)
        await audit(user['username'], 'document.parse', dataset_id)
        return {'accepted': True}

    # 受理单个文档解析请求并记录审计，不等待解析完成。
    @router.post('/api/knowledge/bases/{dataset_id}/documents/{document_id}/parse', status_code=202)
    async def parse_document(dataset_id: RagflowId, document_id: RagflowId,
                             user=Depends(permission('knowledge:write')), knowledge=Depends(service)):
        await knowledge.parse_documents(dataset_id, [document_id])
        await audit(user['username'], 'document.parse', document_id)
        return {'accepted': True}

    # 按请求指定知识库检索，兼容两种 ID 字段并记录返回条数审计。
    @router.post('/api/knowledge/retrieval')
    @router.post('/api/knowledge/search')
    async def search(body: SearchRequest, user=Depends(permission('knowledge:retrieve')),
                     knowledge=Depends(service)):
        result = await knowledge.search(body.query, body.top_k,
                                        body.knowledge_base_ids or body.dataset_ids,
                                        body.similarity_threshold)
        await audit(user['username'], 'knowledge.retrieve', str(len(result['results'])))
        return result

    # 经插件凭证校验后调用共用检索服务，供 OpenClaw Tool 使用。
    @router.post('/knowledge/search')
    async def plugin_search(body: SearchRequest, _=Depends(plugin_guard),
                            knowledge=Depends(service)):
        return await knowledge.search(body.query, body.top_k,
                                      body.knowledge_base_ids or body.dataset_ids,
                                      body.similarity_threshold)

    return router
