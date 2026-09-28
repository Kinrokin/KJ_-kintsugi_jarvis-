"""A bounded importer tick and idle-wait reference; NO production HTTP client."""
from __future__ import annotations
import random
import threading
import time
from .common import BridgeError, Clock, canonical

class ConsumerWorker:
    def __init__(self,gateway,inbox,token:str,clock:Clock|None=None):
        self.gateway,self.inbox,self.token=gateway,inbox,token
        self.clock=clock or Clock()
    def tick(self, *, max_items:int=5, time_budget:float=2.0, fault:str|None=None) -> dict:
        if not 1<=max_items<=5 or not 0<time_budget<=5:
            raise ValueError("invalid tick budget")
        result={"leased":0,"staged":0,"duplicates":0,"acknowledged":0,"errors":[]}
        deadline=self.clock.monotonic()+time_budget
        if self.inbox.summary()["recovering"]:
            result["errors"].append("RESTORE_RECONCILIATION_REQUIRED")
            return result
        for _ in range(max_items):
            if self.clock.monotonic()>=deadline:
                break
            try:
                items=self.gateway.lease(self.token,1)
                if len(canonical(items))>180000:
                    raise BridgeError("RESPONSE_LIMIT")
            except BridgeError as exc:
                result["errors"].append(exc.code)
                break
            if not items:
                break
            envelope=items[0]
            result["leased"]+=1
            if fault=="before_local_commit":
                result["errors"].append("SIMULATED_PROCESS_LOSS")
                break
            try:
                outcome=self.inbox.accept(envelope)
                result["duplicates" if outcome["state"]=="duplicate" else "staged"]+=1
            except BridgeError as exc:
                result["errors"].append(exc.code)
                # Busy/capacity/binding failures remain unacknowledged. Never claim receipt.
                break
            if fault=="after_local_commit":
                result["errors"].append("SIMULATED_PROCESS_LOSS")
                break
            try:
                self.gateway.acknowledge(self.token,envelope["submission_id"],envelope["lease_token"],envelope["sha256"],
                                         fault="after_commit" if fault=="after_ack_commit" else None)
                result["acknowledged"]+=1
            except BridgeError as exc:
                result["errors"].append(exc.code)
                break
        return result

class LocalLongPoll:
    """In-process condition wait for tests; real HTTP long polling is not supplied.
    Call notify after a successful enqueue. Timeouts/reconnect remain necessary.
    """
    def __init__(self,gateway):
        self.gateway=gateway
        self.condition=threading.Condition()
    def notify(self):
        with self.condition:
            self.condition.notify_all()
    def wait(self,token:str,timeout:float=20.0,stop:threading.Event|None=None):
        if not 0<=timeout<=20:
            raise ValueError("wait outside bounds")
        end=time.monotonic()+timeout
        while True:
            with self.condition:
                if stop and stop.is_set():
                    return []
                found=self.gateway.lease(token,1)
                if found:
                    return found
                left=end-time.monotonic()
                if left<=0:
                    return []
                self.condition.wait(min(left,1.0) if stop else left)

def reconnect_delay(attempt:int,rng:random.Random|None=None)->float:
    """Full-jitter bounded delay; trusted host schedules the next attempt."""
    if type(attempt) is not int or not 0<=attempt<=1000:
        raise ValueError("attempt outside bounds")
    return (rng or random).uniform(0.0,min(60.0,2.0**min(attempt,6)))
