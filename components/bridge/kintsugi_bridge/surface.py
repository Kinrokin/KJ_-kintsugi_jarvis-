"""Local application dispatch only. This is NOT an MCP transport/server.

The JSON tool manifest is a future adapter input. A conforming SDK, OAuth
resource-server verifier, HTTP framing and Spark compatibility test remain gates.
"""
from __future__ import annotations
from .common import BridgeError, bounded_json, exact

TOOLS=("jarvis.submit_candidate","jarvis.get_submission_status")
class ProducerSurface:
    def __init__(self,gateway):
        self.gateway=gateway
    def call(self,token:str,name:str,arguments:bytes)->dict:
        # Exact allowlist; not a fragile blacklist of 'execution verbs'.
        if name==TOOLS[0]:
            return self.gateway.submit_candidate(token,arguments)
        if name==TOOLS[1]:
            self.gateway._identity(token,"candidate:status","producer")
            args=exact(bounded_json(arguments,512),{"submission_id"})
            return self.gateway.get_submission_status(token,args["submission_id"])
        raise BridgeError("TOOL_NOT_AVAILABLE")
