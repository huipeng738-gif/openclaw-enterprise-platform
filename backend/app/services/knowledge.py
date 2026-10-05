"""Knowledge access policy and RAGFlow response normalization."""
import os
import re

from fastapi import HTTPException

from app.clients.ragflow import RagflowClient


MANAGED_DATASETS_KEY = 'knowledge:datasets'
ID_PATTERN = re.compile(r'^[a-fA-F0-9]{32}$')


class KnowledgeService:
    # 保存 RAGFlow 客户端和 Redis 连接，供知识库访问控制与管理使用。
    def __init__(self, client: RagflowClient, redis):
        self.client = client
        self.redis = redis

    # 合并环境配置与 Redis knowledge:datasets Set 中的平台托管数据集 ID。
    async def managed_ids(self):
        configured = {item.strip() for item in os.getenv('RAGFLOW_DATASET_IDS', '').split(',')
                      if ID_PATTERN.fullmatch(item.strip())}
        return configured | set(await self.redis.smembers(MANAGED_DATASETS_KEY))

    # 检查 ID 格式及托管范围，拒绝访问未托管的数据集。
    async def require_dataset(self, dataset_id: str):
        if not ID_PATTERN.fullmatch(dataset_id) or dataset_id not in await self.managed_ids():
            raise HTTPException(404, 'knowledge dataset not found')

    # 逐个查询托管数据集，只返回与请求 ID 匹配的记录。
    async def list_datasets(self):
        datasets = []
        for dataset_id in sorted(await self.managed_ids()):
            if not ID_PATTERN.fullmatch(dataset_id):
                continue
            found = await self.client.list_datasets(dataset_id=dataset_id)
            if isinstance(found, list):
                datasets.extend(item for item in found if item.get('id') == dataset_id)
        return datasets

    # 分页读取 RAGFlow 数据集，排除已由平台托管的知识库供管理员关联。
    async def list_available_datasets(self):
        managed = await self.managed_ids()
        available = []
        page = 1
        while page <= 100:
            found = await self.client.list_datasets(page=page, page_size=100)
            if not isinstance(found, list):
                raise HTTPException(502, 'RAGFlow returned invalid dataset list')
            available.extend(item for item in found if isinstance(item, dict)
                             and ID_PATTERN.fullmatch(str(item.get('id', ''))) and item['id'] not in managed)
            if len(found) < 100:
                return available
            page += 1
        raise HTTPException(502, 'RAGFlow dataset list is too large')

    # 确认数据集属于托管范围后读取详情，不存在时返回 404。
    async def get_dataset(self, dataset_id: str):
        await self.require_dataset(dataset_id)
        found = await self.client.get_dataset(dataset_id)
        if found is None:
            raise HTTPException(404, 'knowledge dataset not found')
        return found

    # 删除托管数据集并移除 Redis 登记；环境配置中的数据集需先解除配置。
    async def delete_dataset(self, dataset_id: str):
        await self.get_dataset(dataset_id)
        if dataset_id in {item.strip() for item in os.getenv('RAGFLOW_DATASET_IDS', '').split(',')}:
            raise HTTPException(409, 'remove configured dataset ID before deleting it')
        await self.client.delete_dataset(dataset_id)
        await self.redis.srem(MANAGED_DATASETS_KEY, dataset_id)

    # 创建数据集，校验返回 ID 后加入 Redis 托管集合。
    async def create_dataset(self, name: str):
        created = await self.client.create_dataset(name)
        dataset_id = created.get('id') if isinstance(created, dict) else None
        if not dataset_id or not ID_PATTERN.fullmatch(dataset_id):
            raise HTTPException(502, 'RAGFlow returned an invalid dataset ID')
        await self.redis.sadd(MANAGED_DATASETS_KEY, dataset_id)
        return created

    # 验证已有 RAGFlow 数据集存在后，将其登记到平台托管集合。
    async def register_dataset(self, dataset_id: str):
        if not ID_PATTERN.fullmatch(dataset_id):
            raise HTTPException(422, 'invalid dataset ID')
        found = await self.client.list_datasets(dataset_id=dataset_id)
        if not isinstance(found, list) or not any(item.get('id') == dataset_id for item in found):
            raise HTTPException(404, 'RAGFlow dataset not found')
        await self.redis.sadd(MANAGED_DATASETS_KEY, dataset_id)
        return {'id': dataset_id}

    # 校验数据集访问范围后分页查询文档。
    async def list_documents(self, dataset_id: str, page: int, page_size: int):
        await self.require_dataset(dataset_id)
        return await self.client.list_documents(dataset_id, page=page, page_size=page_size)

    # 校验数据集访问范围后上传文档。
    async def upload_document(self, dataset_id: str, filename: str, content: bytes, content_type: str):
        await self.require_dataset(dataset_id)
        return await self.client.upload_document(dataset_id, filename, content, content_type)

    # 校验数据集范围并读取文档状态，文档不存在时返回 404。
    async def get_document_status(self, dataset_id: str, document_id: str):
        await self.require_dataset(dataset_id)
        document = await self.client.get_document_status(dataset_id, document_id)
        if document is None:
            raise HTTPException(404, 'knowledge document not found')
        return document

    # 确认文档存在且所属数据集可访问后执行删除。
    async def delete_document(self, dataset_id: str, document_id: str):
        await self.get_document_status(dataset_id, document_id)
        await self.client.delete_document(dataset_id, document_id)

    # 逐个确认文档存在后，向 RAGFlow 提交批量解析请求。
    async def parse_documents(self, dataset_id: str, document_ids: list[str]):
        await self.require_dataset(dataset_id)
        for document_id in document_ids:
            await self.get_document_status(dataset_id, document_id)
        return await self.client.parse_documents(dataset_id, document_ids)

    # 限制检索范围为托管数据集，并将分块与引用来源转换为前端和插件共用字段。
    async def search(self, query: str, top_k: int, dataset_ids: list[str] | None,
                     similarity_threshold: float = 0.2):
        managed = await self.managed_ids()
        selected = dataset_ids if dataset_ids is not None else sorted(managed)
        if not selected:
            raise HTTPException(409, 'no knowledge datasets configured')
        if not set(selected).issubset(managed):
            raise HTTPException(403, 'knowledge dataset access denied')
        data = await self.client.retrieve(query, selected, top_k, similarity_threshold)
        if not isinstance(data, dict):
            raise HTTPException(502, 'RAGFlow returned invalid retrieval data')
        results = [
                {'id': item.get('id'), 'dataset_id': item.get('dataset_id') or item.get('kb_id'),
                 'document_id': item.get('document_id'), 'document_name': item.get('document_keyword'),
                 'knowledge_base_id': item.get('dataset_id') or item.get('kb_id'), 'content': item.get('content'),
                 'similarity': item.get('similarity'), 'score': item.get('similarity'),
                 'metadata': item.get('metadata') or {}}
                for item in (data.get('chunks') or [])
                if (item.get('dataset_id') or item.get('kb_id')) in managed
            ]
        return {'query': query, 'total': data.get('total', 0), 'results': results, 'chunks': results}
