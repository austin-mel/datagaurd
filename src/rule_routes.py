from fastapi import APIRouter

from src.persistence_routes import Limit, Offset
from src.rules import RuleSet
from src.schemas import DatasetView, ErrorResponse, Page, RuleAssignment, RuleSetView
from src.services.catalog import Catalog


def rule_router(catalog: Catalog) -> APIRouter:
    router = APIRouter(tags=["Rules"], responses={
        404: {"model": ErrorResponse, "description": "Dataset or rule set not found."},
        422: {"model": ErrorResponse, "description": "Invalid rule configuration or assignment."},
        503: {"model": ErrorResponse, "description": "Database unavailable."},
    })

    @router.post("/rule-sets", response_model=RuleSetView, status_code=201,
                 summary="Create an immutable rule-set revision",
                 description="Reusing a name creates the next revision. Existing dataset assignments stay pinned.")
    def create(request: RuleSet) -> RuleSetView:
        return catalog.create_rule_set(request)

    @router.get("/rule-sets", response_model=Page[RuleSetView], summary="List rule-set revisions")
    def list_rules(limit: Limit = 20, offset: Offset = 0) -> Page[RuleSetView]:
        return catalog.rule_sets(limit, offset)

    @router.get("/rule-sets/{rule_set_id}", response_model=RuleSetView, summary="Get a rule-set revision")
    def get(rule_set_id: str) -> RuleSetView:
        return catalog.rule_set(rule_set_id)

    @router.get("/datasets/{dataset_id}/rule-set", response_model=RuleSetView, summary="Get a dataset's assigned rules")
    def assigned(dataset_id: str) -> RuleSetView:
        return catalog.rule_set(catalog.dataset(dataset_id).rule_set_id)

    @router.put("/datasets/{dataset_id}/rule-set", response_model=DatasetView,
                summary="Assign rules to a dataset",
                description="Future checks, uploads, and corrections use this revision. Historical runs stay unchanged.")
    def assign(dataset_id: str, request: RuleAssignment) -> DatasetView:
        return catalog.assign_rules(dataset_id, request.rule_set_id)

    return router
