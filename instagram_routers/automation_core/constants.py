"""
Constants for Instagram Automations
All hardcoded values, match types, trigger types, and automation types.
"""

# Automation Types - HARDCODED, DO NOT CHANGE
class AutomationType:
    COMMENT_REPLY = "COMMENT_REPLY"
    PRIVATE_MESSAGE = "PRIVATE_MESSAGE"
    DM_REPLY = "DM_REPLY"
    AI_DM_CONVERSATION = "AI_DM_CONVERSATION"


# Trigger Types - HARDCODED, DO NOT CHANGE
class TriggerType:
    KEYWORD = "KEYWORD"
    AI_DECISION = "AI_DECISION"


# Match Types - HARDCODED, DO NOT CHANGE
class MatchType:
    EXACT = "EXACT"
    CONTAINS = "CONTAINS"
    STARTSWITH = "STARTSWITH"
    START_WITH = "START_WITH"  # Alternative naming
    ENDSWITH = "ENDSWITH"
    END_WITH = "END_WITH"  # Alternative naming


# Reply Types - HARDCODED, DO NOT CHANGE
class ReplyType:
    CUSTOM = "CUSTOM"
    AI_DECISION = "AI_DECISION"
    AI_GENERATED = "AI_GENERATED"
    TEMPLATE = "TEMPLATE"
    TEXT = "TEXT"


# Post Selection Types - HARDCODED, DO NOT CHANGE
class PostSelectionType:
    ALL = "ALL"
    SPECIFIC = "SPECIFIC"


# Model Configuration - HARDCODED, DO NOT CHANGE
class ModelConfig:
    DEFAULT_PROVIDER = "OPENAI"
    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 150


# Activation Status - HARDCODED, DO NOT CHANGE
class ActivationStatus:
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PAUSED = "PAUSED"


# Schedule Type - HARDCODED, DO NOT CHANGE
class ScheduleType:
    CONTINUOUS = "CONTINUOUS"
    SCHEDULED = "SCHEDULED"


# Platform - HARDCODED, DO NOT CHANGE
class Platform:
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"


# Model Usage - HARDCODED, DO NOT CHANGE
class ModelUsage:
    PLATFORM_DEFAULT = "PLATFORM_DEFAULT"
    CUSTOM = "CUSTOM"
