"""Chapter 26: opt-in paired score-import evaluation; NEVER runs/loads StepWise.
Scores must be generated externally from comparable, consented observations.
Synthetic fixtures exercise math only, not detector performance.
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def validate(protocol, samples):
    if not isinstance(protocol,dict) or protocol.get("schema_version")!=1:
        raise ValueError("protocol schema_version=1 required")
    if protocol.get("task")!="repeated_failure_review":
        raise ValueError("task mismatch: StepWise stuck label cannot be silently substituted")
    if protocol.get("data_kind") not in ("synthetic","real_reviewed"):
        raise ValueError("data_kind required")
    if protocol.get("annotation_frozen") is not True:
        raise ValueError("labels/protocol not frozen")
    t=protocol.get("threshold")
    if type(t) not in (int,float) or not math.isfinite(t) or not 0<=t<=1:
        raise ValueError("predeclared threshold in [0,1] required")
    if not isinstance(samples,list) or not samples:
        raise ValueError("nonempty sample list required")
    seen=set()
    clusters=defaultdict(set)
    for x in samples:
        if not isinstance(x,dict) or not all(isinstance(x.get(k),str) and x[k]
                    for k in ("sample_id","session_id","split")):
            raise ValueError("sample/session/split required")
        if x["split"] not in ("train","validation","test"):
            raise ValueError("invalid split")
        if x["sample_id"] in seen:
            raise ValueError("duplicate sample")
        seen.add(x["sample_id"])
        clusters[x["session_id"]].add(x["split"])
        if type(x.get("label")) is not int or x["label"] not in (0,1):
            raise ValueError("label must be 0 or 1")
        if type(x.get("rule_alarm")) is not bool:
            raise ValueError("rule_alarm must be bool")
        score=x.get("model_score")
        if score is not None and (type(score) not in (int,float)
                  or not math.isfinite(score) or not 0<=score<=1):
            raise ValueError("bad external model_score")
    if any(len(v)!=1 for v in clusters.values()):
        raise ValueError("session leakage between splits")
    return True


def metrics(rows, field, threshold=None):
    tp=fp=tn=fn=0
    for r in rows:
        v=r[field]
        positive=(v>=threshold) if threshold is not None else v
        if positive and r["label"]==1: tp+=1
        elif positive: fp+=1
        elif r["label"]==1: fn+=1
        else: tn+=1
    precision=tp/(tp+fp) if tp+fp else None
    recall=tp/(tp+fn) if tp+fn else None
    return {"tp":tp,"fp":fp,"tn":tn,"fn":fn,"precision":precision,"recall":recall,
            "f1":2*precision*recall/(precision+recall) if precision is not None
                 and recall is not None and precision+recall>0 else None}


def compare(protocol, samples):
    validate(protocol,samples)
    test=[r for r in samples if r["split"]=="test"]
    if not test:
        return {"status":"NOT_EVALUATED","reason":"no held-out test samples"}
    count_pos=sum(r["label"] for r in test)
    negatives=len(test)-count_pos
    result={"status":"SYNTHETIC_ONLY" if protocol["data_kind"]=="synthetic"
            else "PROVISIONAL_REVIEW_REQUIRED",
            "n_test":len(test),"positives":count_pos,"negatives":negatives,
            "rule":metrics(test,"rule_alarm"),"external_model":"NOT_EVALUATED",
            "model_execution":"NOT_RUN_BY_WATCHDOG",
            "limits":"Labels/scores are user-supplied; task alignment, privacy, calibration and external provenance require review."}
    if any(r.get("model_score") is None for r in test):
        result["reason"]="external model scores missing on held-out rows"
        return result
    result["external_model"]=metrics(test,"model_score",protocol["threshold"])
    result["paired_difference_f1"]=(
        None if result["rule"]["f1"] is None or result["external_model"]["f1"] is None
        else result["external_model"]["f1"]-result["rule"]["f1"])
    gate=protocol.get("min_test_positives")
    if type(gate) is not int or gate<1 or count_pos<gate or negatives<1:
        result["status"]="INSUFFICIENT_FOR_PREDECLARED_GATE"
        result["reason"]="min_test_positives absent/not met or no negatives"
    # This code cannot establish that the samples are real or that the score
    # came from StepWise. Never report VALIDATED/GO based only on a JSON claim.
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--protocol",required=True)
    p.add_argument("--samples",required=True)
    a=p.parse_args()
    print(json.dumps(compare(read_json(a.protocol),read_json(a.samples)),ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
