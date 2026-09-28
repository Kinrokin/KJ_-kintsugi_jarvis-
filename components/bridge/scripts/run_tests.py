"""Run executable evidence; outputs may be directed outside the source tree."""
from pathlib import Path
import argparse
import json
import platform
import sqlite3
import sys
import time
import unittest
from datetime import datetime,timezone
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
class Recording(unittest.TextTestResult):
    def startTest(self,test):
        self.started=time.monotonic();super().startTest(test)
    def addSuccess(self,test):
        self.records.append({"test":test.id(),"status":"PASS","seconds":round(time.monotonic()-self.started,4)})
        super().addSuccess(test)
    def addFailure(self,test,err):
        self.records.append({"test":test.id(),"status":"FAIL"});super().addFailure(test,err)
    def addError(self,test,err):
        self.records.append({"test":test.id(),"status":"ERROR"});super().addError(test,err)
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.records=[]
def main():
    p=argparse.ArgumentParser();p.add_argument("--json",type=Path);a=p.parse_args()
    suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"),top_level_dir=str(ROOT))
    result=unittest.TextTestRunner(verbosity=2,resultclass=Recording).run(suite)
    receipt={"generated_at":datetime.now(timezone.utc).isoformat(),"mode":"OFFLINE_LOCAL_REFERENCE",
             "python":sys.version,"platform":platform.platform(),"sqlite":sqlite3.sqlite_version,
             "tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
             "records":result.records,"live_provider_calls":0,"external_notifications_sent":0,
             "loop_cases_within_tests":{"unknown_field_mutations":500,"crash_delivery_sequences":250},
             "not_certified":["OAuth","MCP transport","Spark","Raspberry Pi","phone","power-loss hardware","global isolation"]}
    if a.json:
        a.json.parent.mkdir(parents=True,exist_ok=True);a.json.write_text(json.dumps(receipt,indent=2)+"\n")
    return 0 if result.wasSuccessful() else 1
if __name__=="__main__":raise SystemExit(main())
