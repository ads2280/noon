from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class AuthenticatedUser(BaseModel):
    """Represents an authenticated user."""
    
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    phone: str
    created_at: datetime
    updated_at: datetime