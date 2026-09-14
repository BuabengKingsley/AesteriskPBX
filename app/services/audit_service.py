import json
import uuid

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record_audit(db: Session, *, customer_id: int | None, event_type: str, action: str, result: str,
                  metadata: dict | None = None, call_id: str | None = None) -> None:
    db.add(AuditEvent(event_id=str(uuid.uuid4()), call_id=call_id, customer_id=customer_id, event_type=event_type,
                      action=action, result=result, event_metadata=json.dumps(metadata or {})))

