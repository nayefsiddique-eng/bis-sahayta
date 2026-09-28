from app.schemas.compliance import QCOResult, RoadmapStep

def generate_roadmap(qco_result: QCOResult) -> list[RoadmapStep]:
    """
    Given a QCOResult, generates an ordered sequence of certification steps.
    Covers document prep -> sample submission -> lab testing -> application -> factory audit & renewal.
    """
    if not qco_result.applies or qco_result.qco_id == "N/A":
        return [
            RoadmapStep(
                step_number=1,
                title="Voluntary Standards Review",
                description="No compulsory QCO currently applies to this product category. You may voluntarily adopt applicable IS standards."
            )
        ]

    steps = [
        RoadmapStep(
            step_number=1,
            title="Document Preparation & Technical Dossier",
            description=f"Gather raw material test reports, factory machinery details, manufacturing process flowcharts, and quality control plan as specified under QCO '{qco_result.qco_id}'."
        ),
        RoadmapStep(
            step_number=2,
            title="Sample Selection & Pre-Testing Audit",
            description=f"Draw representative product samples according to sampling guidelines of standard {qco_result.standard_id}."
        ),
        RoadmapStep(
            step_number=3,
            title="Laboratory Testing",
            description=f"Submit sealed samples to a BIS-recognized testing laboratory to perform all mandatory type tests specified in standard {qco_result.standard_id}."
        ),
        RoadmapStep(
            step_number=4,
            title="Manakonline Application Submission",
            description=f"Submit online application for Scheme-I ISI mark license on BIS Manakonline portal along with test reports, factory layout, and prescribed government application fees."
        ),
        RoadmapStep(
            step_number=5,
            title="BIS Factory Inspection & License Grant",
            description="BIS officer conducts physical or remote factory audit to verify quality infrastructure and testing equipment. Upon successful audit verification, BIS issues the ISI Mark License Certificate."
        ),
        RoadmapStep(
            step_number=6,
            title="License Maintenance & Periodic Renewal",
            description="Affix mandatory ISI mark with CML license number on products/packaging, maintain test records, and submit annual renewal fees."
        )
    ]
    return steps
