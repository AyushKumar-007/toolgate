"""Frozen names shared by every later track. Bump CONTRACT_VERSION to change them."""

from enum import Enum


class Role(str, Enum):
    reader = "reader"
    editor = "editor"
    admin = "admin"


class ToolName(str, Enum):
    list_records = "list_records"
    read_record = "read_record"
    search_records = "search_records"
    create_record = "create_record"
    update_record = "update_record"
    delete_record = "delete_record"
    export_records = "export_records"
    change_permissions = "change_permissions"


class Mode(str, Enum):
    direct = "direct"
    prompt_only = "prompt_only"
    gateway = "gateway"


class Effect(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class RuleId(str, Enum):
    context = "context"
    schema = "schema"
    tenant = "tenant"
    ownership = "ownership"
    actions = "actions"
    arguments = "arguments"
    approval = "approval"
    default = "default"
    prompt_only = "prompt_only"
    direct = "direct"


class Label(str, Enum):
    legitimate = "legitimate"
    attack = "attack"


class ToolStatus(str, Enum):
    ok = "ok"
    error = "error"


READER_TOOLS: frozenset[ToolName] = frozenset(
    {
        ToolName.list_records,
        ToolName.read_record,
        ToolName.search_records,
    }
)
EDITOR_TOOLS: frozenset[ToolName] = READER_TOOLS | frozenset(
    {
        ToolName.create_record,
        ToolName.update_record,
    }
)
ADMIN_TOOLS: frozenset[ToolName] = frozenset(ToolName)

ROLE_ACTIONS: dict[Role, frozenset[ToolName]] = {
    Role.reader: READER_TOOLS,
    Role.editor: EDITOR_TOOLS,
    Role.admin: ADMIN_TOOLS,
}

APPROVAL_REQUIRED: frozenset[ToolName] = frozenset(
    {
        ToolName.delete_record,
        ToolName.export_records,
        ToolName.change_permissions,
    }
)

SEARCH_FIELDS: frozenset[str] = frozenset({"title", "body"})
RECORD_FIELDS: frozenset[str] = frozenset({"title", "body"})

REQUIRED_ARGUMENTS: dict[ToolName, frozenset[str]] = {
    ToolName.list_records: frozenset({"tenant_id"}),
    ToolName.read_record: frozenset({"record_id"}),
    ToolName.search_records: frozenset({"tenant_id", "field", "value"}),
    ToolName.create_record: frozenset({"tenant_id", "owner_id", "title", "body"}),
    ToolName.update_record: frozenset({"record_id", "fields"}),
    ToolName.delete_record: frozenset({"record_id", "approval_token"}),
    ToolName.export_records: frozenset({"tenant_id", "approval_token"}),
    ToolName.change_permissions: frozenset({"user_id", "role", "approval_token"}),
}

POST_TASKS = "/tasks"
GET_AUDIT = "/audit"
POST_APPROVALS = "/approvals"
