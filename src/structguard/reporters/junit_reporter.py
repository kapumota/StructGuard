from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

from structguard.findings import findings_from_report
from structguard.model import ProjectReport


def write_junit_report(report: ProjectReport, path: Path, suite_name: str = "StructGuard Findings") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    findings = findings_from_report(report)
    suite = ET.Element(
        "testsuite",
        {
            "name": suite_name,
            "tests": str(len(findings)),
            "failures": str(sum(finding.severity == "error" for finding in findings)),
            "errors": "0",
            "skipped": str(sum(finding.level == "UNKNOWN" for finding in findings)),
        },
    )
    for index, finding in enumerate(findings):
        testcase = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": (finding.location.file or report.root).replace("/", "."),
                "name": f"{finding.rule_id}:{finding.symbol or index}",
            },
        )
        props = ET.SubElement(testcase, "properties")
        ET.SubElement(props, "property", {"name": "guarantee_level", "value": finding.guarantee.level.value})
        ET.SubElement(props, "property", {"name": "guarantee_label", "value": finding.guarantee.label})
        if finding.severity == "error":
            node = ET.SubElement(testcase, "failure", {"message": finding.message, "type": finding.rule_id})
            node.text = json.dumps(finding.as_dict(), indent=2, ensure_ascii=False)
        elif finding.level == "UNKNOWN":
            node = ET.SubElement(testcase, "skipped", {"message": finding.message})
            node.text = json.dumps(finding.as_dict(), indent=2, ensure_ascii=False)
    tree = ET.ElementTree(suite)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path
