#!/usr/bin/env python3
"""Dependency-free unit/integration-contract suite. No live credentials or accounts."""
import argparse,io,json,platform,sys,time,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
class Result(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.records=[]
    def addSuccess(self,test):super().addSuccess(test);self.records.append({'id':test.id(),'status':'PASS'})
    def addFailure(self,test,err):super().addFailure(test,err);self.records.append({'id':test.id(),'status':'FAIL'})
    def addError(self,test,err):super().addError(test,err);self.records.append({'id':test.id(),'status':'ERROR'})
    def addSkip(self,test,reason):super().addSkip(test,reason);self.records.append({'id':test.id(),'status':'SKIP','reason':reason})
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    stream=io.StringIO();started=time.monotonic();suite=unittest.defaultTestLoader.discover(str(root/'tests'))
    r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(suite)
    report={'scope':'LOCAL_UNIT_AND_MOCK_HTTP_CONTRACTS','tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
            'seconds':time.monotonic()-started,'python':platform.python_version(),'platform':platform.platform(),
            'generated_iterations':{'payload_mutation':1000,'cash_scenarios':500,'mixed_household_commands':300},'live_provider_tests':0,'cases':r.records}
    (out/'TEST_LOG.txt').write_text(stream.getvalue());(out/'TEST_RESULTS.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2));return 0 if r.wasSuccessful() else 1
if __name__=='__main__':sys.exit(main())
