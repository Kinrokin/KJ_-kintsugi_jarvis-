import argparse
import json
from .demo import run_demo

def main():
    parser=argparse.ArgumentParser(description="Kintsugi local bridge review — no server/listener")
    parser.add_argument("command",choices=["demo"])
    parser.parse_args()
    print(json.dumps(run_demo(),indent=2))

if __name__=="__main__":
    main()
