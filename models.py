from typing import Optional

from pydantic import BaseModel


class DocumentPayload(BaseModel):
    document_id: Optional[int]
    document_name: str
    quantity: int
