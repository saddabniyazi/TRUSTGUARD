from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_admin
from app.db.models import PolicyRule, User
from app.db.session import get_db
from app.schemas.policy import PolicyRuleCreate, PolicyRuleOut

router = APIRouter(prefix="/api/rules", tags=["policy-rules"])


@router.get("", response_model=list[PolicyRuleOut])
def list_rules(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[PolicyRule]:
    query = db.query(PolicyRule)
    if active_only:
        query = query.filter(PolicyRule.active.is_(True))
    return query.order_by(PolicyRule.category, PolicyRule.version.desc()).all()


@router.post("", response_model=PolicyRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: PolicyRuleCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> PolicyRule:
    # New rule text in the same category starts a fresh version chain at 1.
    # (A true "supersede this exact rule" flow with version bumps is a
    # reasonable Day 8+ refinement — Day 2 keeps rule creation simple.)
    rule = PolicyRule(category=payload.category, rule_text=payload.rule_text, version=1, active=True)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/{rule_id}/deactivate", response_model=PolicyRuleOut)
def deactivate_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> PolicyRule:
    rule = db.get(PolicyRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy rule not found")
    rule.active = False
    db.commit()
    db.refresh(rule)
    return rule
