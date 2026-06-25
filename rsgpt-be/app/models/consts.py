STREAM_END_FLAG = "--RSGPT-END--"
POSITIVE_FEEDBACK = "positive"
NEGATIVE_FEEDBACK = "negative"
MEDIA_FLAG = "--rsinsight-media--"
LOOKING_FOR_MEDIA_FLAG = "--looking-for-media--"

SOURCE_SELECTIONS = ["ROC", "DIANA", "3GSM", "2SI", "ROCKFIELD", "AQUANTY"]

#questions per license type for an organization
QUESTIONS_PER_FCL_LICENSE = 250
QUESTIONS_PER_PCL_LICENSE = 50
QUESTIONS_FOR_NO_LICENSE = 20

# Agent mode monthly quota for all users (reset on the 1st of each month)
DEFAULT_AGENT_QUOTA = 25

# Client type header value for X-Client-Type
CLIENT_TYPE_BACKEND = "backend"