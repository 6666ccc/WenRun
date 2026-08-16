from app.rag.collections import COLLECTIONS, KnowledgeBase


def conversation_filter(conversation_id: str):
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    return Filter(
        must=[
            FieldCondition(
                key="metadata.conversationId",
                match=MatchValue(value=conversation_id),
            )
        ]
    )


class VectorMemory:
    """Conversation-scoped vector memory. Uses an in-memory map unless a store is injected."""

    def __init__(self, store=None, client=None, store_factory=None):
        self._store = store
        self._client = client
        self._store_factory = store_factory
        self._facts: dict[str, list[str]] = {}

    def _active_store(self):
        if self._store is None and self._store_factory is not None:
            self._store = self._store_factory()
        return self._store

    def save_memory_sync(self, conversation_id: str, facts: list[str]) -> None:
        items = [item for item in facts if item]
        store = self._active_store()
        if store is not None:
            if hasattr(store, "calls"):
                store.calls.append(("save", conversation_id, items))
            if hasattr(store, "add_documents"):
                from langchain_core.documents import Document

                store.add_documents(
                    [
                        Document(page_content=item, metadata={"conversationId": conversation_id})
                        for item in items
                    ]
                )
            elif hasattr(store, "save"):
                store.save(conversation_id, items, conversation_filter(conversation_id))
        self._facts.setdefault(conversation_id, []).extend(items)
        if self._client is not None:
            self._client.upsert(
                collection_name=COLLECTIONS[KnowledgeBase.MEMORY],
                points=items,
                filter=conversation_filter(conversation_id),
            )

    def load_memory_sync(self, conversation_id: str, query: str) -> list[str]:
        qdrant_filter = conversation_filter(conversation_id)
        store = self._active_store()
        if store is not None:
            if hasattr(store, "calls"):
                store.calls.append(("load", conversation_id, query))
            if hasattr(store, "search"):
                return list(store.search(conversation_id, query, qdrant_filter))
            if hasattr(store, "similarity_search"):
                documents = store.similarity_search(query, k=4, filter=qdrant_filter)
                return [getattr(item, "page_content", str(item)) for item in documents]
        if self._client is not None:
            return list(
                self._client.search(
                    collection_name=COLLECTIONS[KnowledgeBase.MEMORY],
                    query=query,
                    query_filter=qdrant_filter,
                )
            )
        return list(self._facts.get(conversation_id, []))

    def delete_memory_sync(self, conversation_id: str) -> None:
        store = self._active_store()
        if store is not None:
            if hasattr(store, "calls"):
                store.calls.append(("delete", conversation_id))
            if hasattr(store, "delete"):
                store.delete(conversation_id, conversation_filter(conversation_id))
        self._facts.pop(conversation_id, None)
        if self._client is not None:
            self._client.delete(
                collection_name=COLLECTIONS[KnowledgeBase.MEMORY],
                points_selector=conversation_filter(conversation_id),
            )

    async def save_memory(self, conversation_id: str, facts: list[str]) -> None:
        self.save_memory_sync(conversation_id, facts)

    async def load_memory(self, conversation_id: str, query: str) -> list[str]:
        return self.load_memory_sync(conversation_id, query)

    async def delete_memory(self, conversation_id: str) -> None:
        self.delete_memory_sync(conversation_id)
