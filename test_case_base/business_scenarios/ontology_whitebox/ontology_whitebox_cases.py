"""Ontology white-box matrix cases.

This file is data only. It declares the inputs and Strict Equal expectations
that the judge runner should apply to OpenClaw's internal white-box output.
"""

EXPECTED_SKILL_ENTITY_TYPES = [
    "Account",
    "Action",
    "Credential",
    "Device",
    "Document",
    "Event",
    "Goal",
    "Location",
    "Message",
    "Note",
    "Organization",
    "Person",
    "Policy",
    "Project",
    "Task",
    "Thread",
]

EXPECTED_SKILL_RELATION_TYPES = [
    "blocks",
    "for_event",
    "has_owner",
    "has_project",
    "has_task", 
    "relate",
]

ENTITY_NAMES_PATH = "kernel.white_box_trace.extraction.extracted_entities[].name"
RELATIONSHIPS_PATH = "kernel.white_box_trace.extraction.extracted_relationships"

TEST_CASES = [
    {
        "case_id": "REAL-001",
        "user_request": "张三去了北京，李四去了上海。",
        "checks": [
            {
                "name": "kernel extracted entity names",
                "path": ENTITY_NAMES_PATH,
                "expected": ["张三", "李四", "北京", "上海"],
            },
            {
                "name": "kernel extracted relationships",
                "path": RELATIONSHIPS_PATH,
                "expected": [],
            },
        ],
    },
    {
        "case_id": "REAL-002",
        "user_request": "张三是李四的朋友，王五是张三的同事。",
        "checks": [
            {
                "name": "kernel extracted entity names",
                "path": ENTITY_NAMES_PATH,
                "expected": ["张三", "李四", "王五"],
            },
            {
                "name": "kernel extracted relationships",
                "path": RELATIONSHIPS_PATH,
                "expected": [],
            },
        ],
    },
    {
        "case_id": "REAL-003",
        "user_request": "查询张三的详细信息",
        "checks": [
            {
                "name": "kernel extracted entity names",
                "path": ENTITY_NAMES_PATH,
                "expected": ["张三"],
            },
            {
                "name": "kernel extracted relationships",
                "path": RELATIONSHIPS_PATH,
                "expected": [],
            },
        ],
    },
    {
        "case_id": "REAL-004",
        "user_request": "北京是中国的首都，马云和马化腾都是知名企业家。",
        "checks": [
            {
                "name": "kernel extracted entity names",
                "path": ENTITY_NAMES_PATH,
                "expected": ["北京", "马云", "马化腾"],
            },
            {
                "name": "kernel extracted relationships",
                "path": RELATIONSHIPS_PATH,
                "expected": [],
            },
        ],
    },
    {
        "case_id": "REAL-005",
        "user_request": "验证 ontology 结构是否完整",
        "checks": [
            {
                "name": "skill md exists",
                "path": "skill.exists",
                "expected": True,
            },
            {
                "name": "skill entity type contract",
                "path": "skill.entity_types",
                "expected": EXPECTED_SKILL_ENTITY_TYPES,
            },
            {
                "name": "skill relation type contract",
                "path": "skill.relation_types",
                "expected": EXPECTED_SKILL_RELATION_TYPES,
            },
            {
                "name": "kernel extracted entity names",
                "path": ENTITY_NAMES_PATH,
                "expected": [],
            },
            {
                "name": "kernel extracted relationships",
                "path": RELATIONSHIPS_PATH,
                "expected": [],
            },
        ],
    },
]
