"""One HTTP boundary for the independently deployed RAGFlow service."""
import logging
import os

import httpx

log = logging.getLogger(__name__)


class RagflowError(Exception):
    # 保存对外响应状态码与错误说明，供 FastAPI 异常处理器使用。
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class RagflowClient:
    # 校验服务配置，创建带认证、超时与连接池限制的异步 HTTP 客户端。
    def __init__(self, base_url: str, api_key: str, transport: httpx.AsyncBaseTransport | None = None,
                 timeout_seconds: float = 30):
        if not base_url.startswith(('http://', 'https://')) or not api_key:
            raise ValueError('RAGFlow URL and API key are required')
        self.http = httpx.AsyncClient(
            base_url=base_url.rstrip('/') + '/',
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=httpx.Timeout(timeout_seconds, connect=min(5, timeout_seconds)),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            transport=transport,
        )

    # 读取 RAGFlow 环境配置；URL 或 API Key 缺失时返回 None。
    @classmethod
    def from_env(cls):
        url = os.getenv('RAGFLOW_BASE_URL', '')
        key = os.getenv('RAGFLOW_API_KEY', '')
        return cls(url, key, timeout_seconds=float(os.getenv('RAGFLOW_TIMEOUT_SECONDS', '30'))) if url and key else None

    # 关闭异步 HTTP 客户端并释放连接池。
    async def close(self):
        await self.http.aclose()

    # 统一执行请求并转换上游错误；检索无分块时返回空结果，其余成功响应提取 data。
    async def _request(self, method: str, path: str, **kwargs):
        try:
            response = await self.http.request(method, path.lstrip('/'), **kwargs)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise RagflowError(504, 'RAGFlow request timed out') from exc
        except httpx.HTTPStatusError as exc:
            log.warning('RAGFlow HTTP request failed: %s %s status=%s', method, path, exc.response.status_code)
            raise RagflowError(502, 'RAGFlow request failed') from exc
        except httpx.RequestError as exc:
            log.warning('RAGFlow HTTP request failed: %s %s', method, path)
            raise RagflowError(502, 'RAGFlow service unavailable') from exc
        except ValueError as exc:
            raise RagflowError(502, 'RAGFlow returned invalid JSON') from exc
        if (method == 'POST' and path == 'api/v1/retrieval' and isinstance(payload, dict)
                and payload.get('code') == 102
                and str(payload.get('message', '')).startswith('No chunk found!')):
            return {'chunks': [], 'total': 0}
        if not isinstance(payload, dict) or payload.get('code') != 0:
            log.warning('RAGFlow business request failed: %s %s code=%s', method, path,
                        payload.get('code') if isinstance(payload, dict) else 'invalid')
            raise RagflowError(502, 'RAGFlow request failed')
        return payload.get('data')

    # 分页查询数据集，可按数据集 ID 筛选。
    async def list_datasets(self, *, page: int = 1, page_size: int = 100, dataset_id: str | None = None):
        params = {'page': page, 'page_size': page_size}
        if dataset_id:
            params['id'] = dataset_id
        return await self._request('GET', 'api/v1/datasets', params=params)

    # 调用 RAGFlow 创建指定名称的数据集。
    async def create_dataset(self, name: str):
        return await self._request('POST', 'api/v1/datasets', json={'name': name})

    # 按 ID 查询并返回匹配的数据集，不存在时返回 None。
    async def get_dataset(self, dataset_id: str):
        found = await self.list_datasets(dataset_id=dataset_id)
        return next((item for item in found if item.get('id') == dataset_id), None) if isinstance(found, list) else None

    # 调用 RAGFlow 删除指定数据集。
    async def delete_dataset(self, dataset_id: str):
        return await self._request('DELETE', 'api/v1/datasets', json={'ids': [dataset_id]})

    # 分页查询数据集内文档，可按文档 ID 筛选。
    async def list_documents(self, dataset_id: str, *, page: int = 1, page_size: int = 30,
                             document_id: str | None = None):
        params = {'page': page, 'page_size': page_size}
        if document_id:
            params['id'] = document_id
        return await self._request('GET', f'api/v1/datasets/{dataset_id}/documents',
                                   params=params)

    # 通过 multipart 请求上传文档内容及文件类型。
    async def upload_document(self, dataset_id: str, filename: str, content: bytes, content_type: str):
        return await self._request('POST', f'api/v1/datasets/{dataset_id}/documents',
                                   files={'file': (filename, content, content_type)})

    # 调用 RAGFlow 删除数据集中的指定文档。
    async def delete_document(self, dataset_id: str, document_id: str):
        return await self._request('DELETE', f'api/v1/datasets/{dataset_id}/documents',
                                   json={'ids': [document_id]})

    # 提交文档解析请求，分块处理由 RAGFlow 执行。
    async def parse_documents(self, dataset_id: str, document_ids: list[str]):
        return await self._request('POST', f'api/v1/datasets/{dataset_id}/chunks',
                                   json={'document_ids': document_ids})

    # 查询指定文档的当前信息与解析状态，不存在时返回 None。
    async def get_document_status(self, dataset_id: str, document_id: str):
        data = await self.list_documents(dataset_id, document_id=document_id)
        return next((item for item in data.get('docs', []) if item.get('id') == document_id), None) if isinstance(data, dict) else None

    # 在指定数据集中检索分块，将结果数量映射为 page_size 并传递相似度阈值。
    async def retrieve(self, query: str, dataset_ids: list[str], limit: int,
                       similarity_threshold: float = 0.2):
        return await self._request('POST', 'api/v1/retrieval',
                                   json={'question': query, 'dataset_ids': dataset_ids,
                                         'page': 1, 'page_size': limit,
                                         'similarity_threshold': similarity_threshold})
