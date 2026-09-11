"""
Mock InfoExchange (Shield) API for Development/Testing
Mimics the real InfoExchange (EcoOnline Shield) API behavior for testing the
Shield extraction pipeline in dev, since EcoOnline does not provide a
separate dev/sandbox tenant.

Endpoints mocked:
    POST /identity/connect/token
        - OAuth2 client_credentials grant (any client_id/client_secret accepted)
    GET  /api/v0/riskAssessments/identifiedRisk
        - JSON:API-shaped response with sample records
        - Supports page[limit] / page[offset] query params
    GET  /api/v0/incidentReporting/incidents
        - JSON:API-shaped response with sample records
        - Supports page[limit] / page[offset] query params
    GET  /api/v0/riskAssessments/riskAssessment
        - JSON:API-shaped response with sample records
        - Supports page[limit] / page[offset] query params
    GET  /api/v0/incidentReporting/injuredPerson
        - JSON:API-shaped response with sample records
        - Supports page[limit] / page[offset] query params
    GET  /health
        - Health check

Usage (local):
    python3 main.py
    (listens on 0.0.0.0:8080)

Usage (once deployed to Cloud Run):
    SHIELD_BASE_URL=https://<cloud-run-url> CLIENT_ID=anything CLIENT_SECRET=anything BUCKET_ENV=dev \
    bash shield_identifiedrisk_get_mocktest.bash
    (or shield_incidents_get_mocktest.bash /
     shield_riskassessment_get_mocktest.bash /
     shield_injuredperson_get_mocktest.bash for the other 3 endpoints)
"""

from flask import Flask, jsonify, request
from datetime import datetime
import uuid

app = Flask(__name__)


def get_standard_headers():
    """Generate standard response headers matching real API format."""
    return {
        'Date': datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT'),
        'Content-Type': 'application/vnd.api+json',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-store',
        'X-Request-Id': uuid.uuid4().hex,
    }


# ------------------------------------------------------------------
# Sample data - rebuilt from the REAL field structure of a
# riskAssessments/identifiedRisk record (confirmed against an actual
# prod sample), with entirely fictional values. Field names are
# preserved exactly, including known quirks (e.g. the field named
# "riskRatingafterControlMeasuresactionsSafet" - not a typo here,
# this matches the real API's actual field name so parsing logic
# is tested faithfully).
# ------------------------------------------------------------------
IDENTIFIED_RISK_DATA = [
    {
        "id": "70001",
        "type": "identifiedRisk",
        "attributes": {
            "identifiedRiskRefNo": 88801,
            "riskName": "Trip hazard, minor injury from loose flooring",
            "risksToHealth": None,
            "risksToSafety": None,
            "riskRatingBeforeControlMeasuresActions": {
                "text": "Medium",
                "colour": "#FFFF00"
            },
            "technicalControlMeasures": None,
            "organisationalControlMeasures": None,
            "proceduralControlMeasures": None,
            "status": {
                "text": "Complete",
                "colour": "#00FF00"
            },
            "lastUpdatedOn": "2026-05-14T10:12:00",
            "lastUpdatedBy": "Test User One",
            "riskRatingAfterControlMeasuresActions": {
                "text": "Low",
                "colour": "#00FF00"
            },
            "riskDescription": "Sample fictional description: uneven flooring in a test venue corridor requiring signage and inspection.",
            "riskRatingBeforeControlMeasuresactionsSafety": {
                "text": "",
                "colour": None
            },
            "riskRatingafterControlMeasuresactionsSafet": {
                "text": "",
                "colour": None
            },
            "risksToHealthAfter": None,
            "risksToSafetyAfterControlMeasures": None,
            "personalProtectiveEquipment": None,
            "hazardCategoryuserDefinedHazard": "Slips and Trips",
            "tickToConfirmAllFieldsCompleted": True,
            "conditionalLogicFormattedText": None,
            "suggestedControlMeasures": "Sample fictional control measures text: inspect flooring regularly, place warning signage, report any damage to site management immediately."
        },
        "relationships": {
            "riskAssessmentRefNo": {
                "data": {"type": "riskAssessment", "id": "77001", "meta": {"displayValue": 9999}},
                "links": {"related": "/api/v0/riskAssessments/riskAssessment/77001"}
            },
            "hazardDocument": {"data": None},
            "likelihood": {
                "data": {"type": "luLikelihood", "id": "2", "meta": {"displayValue": "2 - Unlikely"}},
                "links": {"related": "/api/v0/riskAssessments/luLikelihood/2"}
            },
            "likelihoodAfterControl": {
                "data": {"type": "luLikelihood", "id": "1", "meta": {"displayValue": "1 - Remote"}},
                "links": {"related": "/api/v0/riskAssessments/luLikelihood/1"}
            },
            "severity": {
                "data": {"type": "luRiskSeverity", "id": "2", "meta": {"displayValue": "2 - Minor"}},
                "links": {"related": "/api/v0/riskAssessments/luRiskSeverity/2"}
            },
            "severityAfterControl": {
                "data": {"type": "luRiskSeverity", "id": "1", "meta": {"displayValue": "1 - Negligible"}},
                "links": {"related": "/api/v0/riskAssessments/luRiskSeverity/1"}
            },
            "likelihoodSafety": {"data": None},
            "severitySafety": {"data": None},
            "likelihoodAfterControlSafety": {"data": None},
            "severityAfterControlSafety": {"data": None},
            "sys_calculations": {
                "links": {"related": "/api/v0/riskAssessments/identifiedRisk/70001/sys_calculations"}
            }
        },
        "links": {"self": "/api/v0/riskAssessments/identifiedRisk/70001"}
    },
    {
        "id": "70002",
        "type": "identifiedRisk",
        "attributes": {
            "identifiedRiskRefNo": 88802,
            "riskName": "Manual handling, back strain from lifting test equipment",
            "risksToHealth": None,
            "risksToSafety": None,
            "riskRatingBeforeControlMeasuresActions": {
                "text": "Medium High",
                "colour": "#FFA322"
            },
            "technicalControlMeasures": None,
            "organisationalControlMeasures": None,
            "proceduralControlMeasures": None,
            "status": {
                "text": "In Progress",
                "colour": "#FFA500"
            },
            "lastUpdatedOn": "2026-06-02T09:30:00",
            "lastUpdatedBy": "Test User Two",
            "riskRatingAfterControlMeasuresActions": {
                "text": "Medium",
                "colour": "#FFFF00"
            },
            "riskDescription": "Sample fictional description: crew occasionally required to lift equipment cases exceeding recommended weight without assistance.",
            "riskRatingBeforeControlMeasuresactionsSafety": {
                "text": "",
                "colour": None
            },
            "riskRatingafterControlMeasuresactionsSafet": {
                "text": "",
                "colour": None
            },
            "risksToHealthAfter": None,
            "risksToSafetyAfterControlMeasures": None,
            "personalProtectiveEquipment": None,
            "hazardCategoryuserDefinedHazard": "Manual Handling",
            "tickToConfirmAllFieldsCompleted": True,
            "conditionalLogicFormattedText": None,
            "suggestedControlMeasures": "Sample fictional control measures text: use two-person lifting for cases over 20kg, provide manual handling training, use trolleys where available."
        },
        "relationships": {
            "riskAssessmentRefNo": {
                "data": {"type": "riskAssessment", "id": "77002", "meta": {"displayValue": 9998}},
                "links": {"related": "/api/v0/riskAssessments/riskAssessment/77002"}
            },
            "hazardDocument": {"data": None},
            "likelihood": {
                "data": {"type": "luLikelihood", "id": "3", "meta": {"displayValue": "3 - Possible"}},
                "links": {"related": "/api/v0/riskAssessments/luLikelihood/3"}
            },
            "likelihoodAfterControl": {
                "data": {"type": "luLikelihood", "id": "2", "meta": {"displayValue": "2 - Unlikely"}},
                "links": {"related": "/api/v0/riskAssessments/luLikelihood/2"}
            },
            "severity": {
                "data": {"type": "luRiskSeverity", "id": "3", "meta": {"displayValue": "3 - Moderate"}},
                "links": {"related": "/api/v0/riskAssessments/luRiskSeverity/3"}
            },
            "severityAfterControl": {
                "data": {"type": "luRiskSeverity", "id": "2", "meta": {"displayValue": "2 - Minor"}},
                "links": {"related": "/api/v0/riskAssessments/luRiskSeverity/2"}
            },
            "likelihoodSafety": {"data": None},
            "severitySafety": {"data": None},
            "likelihoodAfterControlSafety": {"data": None},
            "severityAfterControlSafety": {"data": None},
            "sys_calculations": {
                "links": {"related": "/api/v0/riskAssessments/identifiedRisk/70002/sys_calculations"}
            }
        },
        "links": {"self": "/api/v0/riskAssessments/identifiedRisk/70002"}
    },
]

IDENTIFIED_RISK_TOTAL_COUNT = 20621  # mimics real prod totalCount seen during testing


# ------------------------------------------------------------------
# Sample data - rebuilt from the REAL field structure of an
# incidentReporting/incidents record (confirmed against an actual
# prod sample), with entirely fictional values. All names, emails,
# addresses, and reference numbers below are fictional. Field names
# are preserved exactly, including the many relationship fields with
# null data (these mirror real optional/unused fields on the record).
# ------------------------------------------------------------------
INCIDENTS_DATA = [
    {
        "id": "50001",
        "type": "incidents",
        "attributes": {
            "dateAndTimeIncidentReported": "2026-02-10T09:15:00",
            "otherReportingPersonType": None,
            "nameOfPersonCompletingThisForm": "Sample Tester One",
            "emailAddress": "sample.tester.one@example-corp.test",
            "phoneNumber": None,
            "dateAndTimeOfIncident": "2026-02-10T08:00:00",
            "otherIncidentLocation": None,
            "exactLocation": "1 Test Avenue, Sampleton, TS1 1AA",
            "incidentDescriptionPleaseDescribeInDetail": "Sample fictional incident: a test employee reported a minor equipment issue during a routine site visit.",
            "otherImmediateCause": None,
            "tickIfYouWishToRemainAnonymous": None,
            "firstDayOfLostTime": None,
            "lastDayOfLostTime": None,
            "otherPurposeOfTravelVehicleUsed": None,
            "registrationNumberOfVehicleInvolved": None,
            "yourVehicleDamageDetails": None,
            "registrationNumberOfThirdPartyVehicle": None,
            "thirdPartyVehicleDamageDetails": None,
            "otherTypeOfDamage": None,
            "howLongDidItTakeForTheBuilding": None,
            "generalFeedbackOnPepPlans": None,
            "generalCommentsOnEvacuation": None,
            "incidentStatus": {"text": "Closed", "colour": "#00FF00"},
            "lastUpdatedOn": "2026-02-14T11:20:00",
            "lastUpdatedBy": "Sample Reviewer One",
            "incidentRefNoPrefix": "TST - 001",
            "severityOfIncident": {"text": "P3", "colour": "#FFFF00"},
            "calculatedDaysOff": None,
            "whereAppropriatePleaseEnterFurtherDetails": "T0001",
            "departmentNotListed": None,
            "otherRetailType": None,
            "conditionalLogic": None,
            "germanWorkRelatedIllHealthConditionalLogic": None,
            "conditionalLogicSupportingDocuments": None,
            "conditionalLogicInjuredPerson": None,
            "reportedByGric": None,
            "reportedByHomeServiceHelpdesk": None
        },
        "relationships": {
            "pleaseSelectWhichDescriptionOfTheIncident": {"data": None},
            "pleaseSelectTheMostAppropriateDescription": {"data": None},
            "reportingPersonType": {
                "data": {"type": "luReportingPersonType", "id": "1", "meta": {"displayValue": "Employee"}},
                "links": {"related": "/api/v0/incidentReporting/luReportingPersonType/1"}
            },
            "incidentLocation": {
                "data": {"type": "luIncidentLocation", "id": "1", "meta": {"displayValue": "Field Service"}},
                "links": {"related": "/api/v0/incidentReporting/luIncidentLocation/1"}
            },
            "incidentSubLocation": {
                "data": {"type": "luIncidentSubLocation", "id": "3", "meta": {"displayValue": "Domestic Property"}},
                "links": {"related": "/api/v0/incidentReporting/luIncidentSubLocation/3"}
            },
            "locationType": {
                "data": {"type": "luLocationDetail", "id": "3", "meta": {"displayValue": "Inside the property"}},
                "links": {"related": "/api/v0/incidentReporting/luLocationDetail/3"}
            },
            "immediateCause": {
                "data": {"type": "luImmediateCause", "id": "9", "meta": {"displayValue": "Property Damage - Customer Property"}},
                "links": {"related": "/api/v0/incidentReporting/luImmediateCause/9"}
            },
            "didTheIncidentOccurWhilstCommutingToOrFrom": {"data": None},
            "didTheEmergencyServicesAttendThisIncident": {
                "data": {"type": "luYesNo", "id": "2", "meta": {"displayValue": "No"}},
                "links": {"related": "/api/v0/incidentReporting/luYesNo/2"}
            },
            "employeeNameOfIllHealthPerson": {"data": None},
            "pleaseSelectTheNatureOfTheWorkRelatedIll": {"data": None},
            "hasTheConditionBeenDiagnosedByADrOr": {"data": None},
            "pleaseSelectTheTypeOfIncident": {"data": None},
            "wasAnAmbulanceCalled": {"data": None},
            "wasThisPersonPlacedOnRestrictedOrLight": {"data": None},
            "whatWasThePurposeOfYourTravelVehicleBeing": {"data": None},
            "wereThereAnyInjuredPersonsIps": {"data": None},
            "ipsTakenByAmbulance": {"data": None},
            "wasYourVehicleDamaged": {"data": None},
            "wasAThirdPartyVehicleInvolved": {"data": None},
            "wasTheThirdPartyVehicleDamaged": {"data": None},
            "typeOfDamage": {
                "data": {"type": "luTypeOfDamage", "id": "2", "meta": {"displayValue": "Services Damage (water, electricity, gas)"}},
                "links": {"related": "/api/v0/incidentReporting/luTypeOfDamage/2"}
            },
            "didTheBuildingEvacuate": {"data": None},
            "wereThereAnyPersonsWithPepPlansInTheBuild": {"data": None},
            "incidentType": {
                "data": {"type": "luIncidentTypeAndDescription", "id": "47", "meta": {"displayValue": "Damage to property arising from work activities"}},
                "links": {"related": "/api/v0/incidentReporting/luIncidentTypeAndDescription/47"}
            },
            "whatWasThePotentialSeverityOfTheIssue": {"data": None},
            "thisALostTimeInjury": {"data": None},
            "retailType": {"data": None},
            "italyIncidentCategory": {"data": None},
            "inailRejected": {"data": None},
            "nonCriticalHitType": {"data": None},
            "luImmediateCause": {"links": {"related": "/api/v0/incidentReporting/incidents/50001/luImmediateCause"}},
            "luWeatherConditions": {"links": {"related": "/api/v0/incidentReporting/incidents/50001/luWeatherConditions"}},
            "luEmergencyServices": {"links": {"related": "/api/v0/incidentReporting/incidents/50001/luEmergencyServices"}},
            "employees": {"links": {"related": "/api/v0/incidentReporting/incidents/50001/employees"}},
            "sys_calculations": {"links": {"related": "/api/v0/incidentReporting/incidents/50001/sys_calculations"}}
        },
        "links": {"self": "/api/v0/incidentReporting/incidents/50001"}
    },
    {
        "id": "50002",
        "type": "incidents",
        "attributes": {
            "dateAndTimeIncidentReported": "2026-03-05T14:22:00",
            "otherReportingPersonType": None,
            "nameOfPersonCompletingThisForm": "Sample Tester Two",
            "emailAddress": "sample.tester.two@example-corp.test",
            "phoneNumber": None,
            "dateAndTimeOfIncident": "2026-03-05T11:00:00",
            "otherIncidentLocation": None,
            "exactLocation": "2 Test Boulevard, Sampleton, TS2 2BB",
            "incidentDescriptionPleaseDescribeInDetail": "Sample fictional incident: a test field engineer temporarily left equipment unattended near a walkway before promptly relocating it to a safe position after being reminded of procedure.",
            "otherImmediateCause": None,
            "tickIfYouWishToRemainAnonymous": None,
            "firstDayOfLostTime": None,
            "lastDayOfLostTime": None,
            "otherPurposeOfTravelVehicleUsed": None,
            "registrationNumberOfVehicleInvolved": None,
            "yourVehicleDamageDetails": None,
            "registrationNumberOfThirdPartyVehicle": None,
            "thirdPartyVehicleDamageDetails": None,
            "otherTypeOfDamage": None,
            "howLongDidItTakeForTheBuilding": None,
            "generalFeedbackOnPepPlans": None,
            "generalCommentsOnEvacuation": None,
            "incidentStatus": {"text": "Closed", "colour": "#00FF00"},
            "lastUpdatedOn": "2026-03-09T10:05:00",
            "lastUpdatedBy": "Sample Reviewer Two",
            "incidentRefNoPrefix": "TST - 002",
            "severityOfIncident": {"text": "P3", "colour": "#FFFF00"},
            "calculatedDaysOff": None,
            "whereAppropriatePleaseEnterFurtherDetails": "T0002",
            "departmentNotListed": None,
            "otherRetailType": None,
            "conditionalLogic": None,
            "germanWorkRelatedIllHealthConditionalLogic": None,
            "conditionalLogicSupportingDocuments": None,
            "conditionalLogicInjuredPerson": None,
            "reportedByGric": None,
            "reportedByHomeServiceHelpdesk": None
        },
        "relationships": {
            "pleaseSelectWhichDescriptionOfTheIncident": {"data": None},
            "pleaseSelectTheMostAppropriateDescription": {"data": None},
            "reportingPersonType": {
                "data": {"type": "luReportingPersonType", "id": "1", "meta": {"displayValue": "Employee"}},
                "links": {"related": "/api/v0/incidentReporting/luReportingPersonType/1"}
            },
            "incidentLocation": {
                "data": {"type": "luIncidentLocation", "id": "1", "meta": {"displayValue": "Field Service"}},
                "links": {"related": "/api/v0/incidentReporting/luIncidentLocation/1"}
            },
            "incidentSubLocation": {
                "data": {"type": "luIncidentSubLocation", "id": "3", "meta": {"displayValue": "Domestic Property"}},
                "links": {"related": "/api/v0/incidentReporting/luIncidentSubLocation/3"}
            },
            "locationType": {
                "data": {"type": "luLocationDetail", "id": "4", "meta": {"displayValue": "Outside the property"}},
                "links": {"related": "/api/v0/incidentReporting/luLocationDetail/4"}
            },
            "immediateCause": {"data": None},
            "didTheIncidentOccurWhilstCommutingToOrFrom": {"data": None},
            "didTheEmergencyServicesAttendThisIncident": {
                "data": {"type": "luYesNo", "id": "2", "meta": {"displayValue": "No"}},
                "links": {"related": "/api/v0/incidentReporting/luYesNo/2"}
            },
            "employeeNameOfIllHealthPerson": {"data": None},
            "pleaseSelectTheNatureOfTheWorkRelatedIll": {"data": None},
            "hasTheConditionBeenDiagnosedByADrOr": {"data": None},
            "pleaseSelectTheTypeOfIncident": {"data": None},
            "wasAnAmbulanceCalled": {"data": None},
            "wasThisPersonPlacedOnRestrictedOrLight": {"data": None},
            "whatWasThePurposeOfYourTravelVehicleBeing": {"data": None},
            "wereThereAnyInjuredPersonsIps": {"data": None},
            "ipsTakenByAmbulance": {"data": None},
            "wasYourVehicleDamaged": {"data": None},
            "wasAThirdPartyVehicleInvolved": {"data": None},
            "wasTheThirdPartyVehicleDamaged": {"data": None},
            "typeOfDamage": {"data": None},
            "didTheBuildingEvacuate": {"data": None},
            "wereThereAnyPersonsWithPepPlansInTheBuild": {"data": None},
            "incidentType": {
                "data": {"type": "luIncidentTypeAndDescription", "id": "48", "meta": {"displayValue": "An event that did not cause harm but had the potential to cause injury or ill health"}},
                "links": {"related": "/api/v0/incidentReporting/luIncidentTypeAndDescription/48"}
            },
            "whatWasThePotentialSeverityOfTheIssue": {
                "data": {"type": "luNearMissSeverity", "id": "3", "meta": {"displayValue": "An incident which did not, but which could have caused harm/damage to an individual or property"}},
                "links": {"related": "/api/v0/incidentReporting/luNearMissSeverity/3"}
            },
            "thisALostTimeInjury": {"data": None},
            "retailType": {"data": None},
            "italyIncidentCategory": {"data": None},
            "inailRejected": {"data": None},
            "nonCriticalHitType": {"data": None},
            "luImmediateCause": {"links": {"related": "/api/v0/incidentReporting/incidents/50002/luImmediateCause"}},
            "luWeatherConditions": {"links": {"related": "/api/v0/incidentReporting/incidents/50002/luWeatherConditions"}},
            "luEmergencyServices": {"links": {"related": "/api/v0/incidentReporting/incidents/50002/luEmergencyServices"}},
            "employees": {"links": {"related": "/api/v0/incidentReporting/incidents/50002/employees"}},
            "sys_calculations": {"links": {"related": "/api/v0/incidentReporting/incidents/50002/sys_calculations"}}
        },
        "links": {"self": "/api/v0/incidentReporting/incidents/50002"}
    },
]

INCIDENTS_TOTAL_COUNT = 6321  # fictional total, deliberately different from real prod count


# ------------------------------------------------------------------
# Sample data - rebuilt from the REAL field structure of a
# riskAssessments/riskAssessment record (confirmed against an actual
# prod sample), with entirely fictional values. All company/brand
# references, employee names, and assessment content below are
# fictional. Field names preserved exactly.
# ------------------------------------------------------------------
RISK_ASSESSMENT_DATA = [
    {
        "id": "80001",
        "type": "riskAssessment",
        "attributes": {
            "riskAssessmentRefNo": 9101,
            "dateCreated": "2026-01-10T00:00:00",
            "otherRiskAssessmentCategory": None,
            "assessmentTitle": "Sample Fictional Assessment - Field Operations Category A, Test Period 2026",
            "assessmentOutlineDescriptionOfActivitiesUnder": "Sample fictional description: this assessment covers a generic set of field operations activities for testing purposes, including standard travel, on-site work, and routine coordination between test teams. No real operational content is contained here - all details are placeholder text for pipeline validation.",
            "assessmentStartDate": "2026-01-10T00:00:00",
            "approximateAssessmentEndDate": None,
            "planForTrip": None,
            "commsPlan": None,
            "accommodation": None,
            "emergencyPlan": None,
            "otherPeopleAtRisk": None,
            "onSiteLocation": None,
            "offSiteProvideDetail": "Sample fictional deployments with a generic test rating.",
            "status": {"text": "Archived", "colour": "#808080"},
            "lastUpdatedOn": "2026-01-20T09:00:00",
            "lastUpdatedBy": "Sample Assessor One",
            "travellerMlreConditionalLogic": None,
            "additionalInformation": False,
            "assessmentOutlinedescriptionOfActivitiesCont": None,
            "peopleAtRiskDetails": None,
            "supportingEvidenceMlreConditionalLogic": None,
            "tickWhenReadyForApproval": False,
            "acknowledgmentRequired": None,
            "numberOfAcknowledgementsRemaining": 0,
            "tickToCloseDownAssessment": None,
            "teamHaveDepartedFromTheCountryOfDeployment": None,
            "trackingClosedDown": None,
            "ppeReturnedAndCheckedInOnCheqroom": None,
            "nokRemovedFromTheDatabase": None,
            "comms": None,
            "equipment": None,
            "training": None,
            "other": None,
            "teamFeedback": None,
            "secondaryHighRiskAssessmentApproval": None
        },
        "relationships": {
            "riskAssessmentCategory": {
                "data": {"type": "luRiskAssessmentCategory", "id": "3", "meta": {"displayValue": "Category A"}},
                "links": {"related": "/api/v0/riskAssessments/luRiskAssessmentCategory/3"}
            },
            "uploadAttachment": {"data": None},
            "isThisAnAdHocOrOnGoingRiskAssessment": {
                "data": {"type": "luAdHocOnGoing", "id": "2", "meta": {"displayValue": "Long Term"}},
                "links": {"related": "/api/v0/riskAssessments/luAdHocOnGoing/2"}
            },
            "emergencyPlanAttachment": {"data": None},
            "updates": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/sys_discussionForumPosts/updates"}},
            "feedback": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/sys_discussionForumPosts/feedback"}},
            "uploadAttachment2": {"data": None},
            "uploadAttachment3": {"data": None},
            "primaryAssessor": {
                "data": {"type": "employees", "id": "99001", "meta": {"displayValue": "Sample Assessor One"}},
                "links": {"related": "/api/v0/riskAssessments/employees/99001"}
            },
            "jobProfile": {"data": None},
            "nextReviewmonths": {
                "data": {"type": "luFrequencyOfReview", "id": "12", "meta": {"displayValue": 12}},
                "links": {"related": "/api/v0/riskAssessments/luFrequencyOfReview/12"}
            },
            "market": {
                "data": {"type": "luMarket", "id": "1", "meta": {"displayValue": "Test Region"}},
                "links": {"related": "/api/v0/riskAssessments/luMarket/1"}
            },
            "marketAreaResponsible": {
                "data": {"type": "luMarket", "id": "1", "meta": {"displayValue": "Test Region"}},
                "links": {"related": "/api/v0/riskAssessments/luMarket/1"}
            },
            "luPeopleAtRisk": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luPeopleAtRisk"}},
            "mtmGenericAssessment": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/mtmGenericAssessment"}},
            "employees": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/employees"}},
            "luFreelancers": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luFreelancers"}},
            "luDirectorate": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luDirectorate"}},
            "luLocationOfRisks": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luLocationOfRisks"}},
            "luOnSiteBuilding": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luOnSiteBuilding"}},
            "luHighRiskType": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luHighRiskType"}},
            "luLocationsRa": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luLocationsRa"}},
            "luLessonsIdentified": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/luLessonsIdentified"}},
            "sys_calculations": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80001/sys_calculations"}}
        },
        "links": {"self": "/api/v0/riskAssessments/riskAssessment/80001"}
    },
    {
        "id": "80002",
        "type": "riskAssessment",
        "attributes": {
            "riskAssessmentRefNo": 9102,
            "dateCreated": "2026-01-18T00:00:00",
            "otherRiskAssessmentCategory": None,
            "assessmentTitle": "Sample Fictional Assessment - Standard Operations Generic Assessment",
            "assessmentOutlineDescriptionOfActivitiesUnder": "Sample fictional description: this generic assessment covers standard, low-risk test activities. DISTRIBUTION: for use by fictional test teams only. USE: for standard, low-risk sample assignments. EXCEPTIONS: outside these definitions a bespoke assessment must be considered. All content here is placeholder text for pipeline validation purposes only.",
            "assessmentStartDate": "2026-01-18T00:00:00",
            "approximateAssessmentEndDate": None,
            "planForTrip": None,
            "commsPlan": None,
            "accommodation": None,
            "emergencyPlan": None,
            "otherPeopleAtRisk": None,
            "onSiteLocation": None,
            "offSiteProvideDetail": "Sample fictional coverage across generic test locations.",
            "status": {"text": "Archived", "colour": "#808080"},
            "lastUpdatedOn": "2026-02-01T10:00:00",
            "lastUpdatedBy": "Sample Assessor Two",
            "travellerMlreConditionalLogic": None,
            "additionalInformation": False,
            "assessmentOutlinedescriptionOfActivitiesCont": None,
            "peopleAtRiskDetails": None,
            "supportingEvidenceMlreConditionalLogic": None,
            "tickWhenReadyForApproval": True,
            "acknowledgmentRequired": False,
            "numberOfAcknowledgementsRemaining": 0,
            "tickToCloseDownAssessment": None,
            "teamHaveDepartedFromTheCountryOfDeployment": None,
            "trackingClosedDown": None,
            "ppeReturnedAndCheckedInOnCheqroom": None,
            "nokRemovedFromTheDatabase": None,
            "comms": None,
            "equipment": None,
            "training": None,
            "other": None,
            "teamFeedback": None,
            "secondaryHighRiskAssessmentApproval": None
        },
        "relationships": {
            "riskAssessmentCategory": {
                "data": {"type": "luRiskAssessmentCategory", "id": "1", "meta": {"displayValue": "Category B"}},
                "links": {"related": "/api/v0/riskAssessments/luRiskAssessmentCategory/1"}
            },
            "uploadAttachment": {"data": None},
            "isThisAnAdHocOrOnGoingRiskAssessment": {
                "data": {"type": "luAdHocOnGoing", "id": "2", "meta": {"displayValue": "Long Term"}},
                "links": {"related": "/api/v0/riskAssessments/luAdHocOnGoing/2"}
            },
            "emergencyPlanAttachment": {"data": None},
            "updates": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/sys_discussionForumPosts/updates"}},
            "feedback": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/sys_discussionForumPosts/feedback"}},
            "uploadAttachment2": {"data": None},
            "uploadAttachment3": {"data": None},
            "primaryAssessor": {
                "data": {"type": "employees", "id": "99002", "meta": {"displayValue": "Sample Assessor Two"}},
                "links": {"related": "/api/v0/riskAssessments/employees/99002"}
            },
            "jobProfile": {"data": None},
            "nextReviewmonths": {
                "data": {"type": "luFrequencyOfReview", "id": "12", "meta": {"displayValue": 12}},
                "links": {"related": "/api/v0/riskAssessments/luFrequencyOfReview/12"}
            },
            "market": {
                "data": {"type": "luMarket", "id": "1", "meta": {"displayValue": "Test Region"}},
                "links": {"related": "/api/v0/riskAssessments/luMarket/1"}
            },
            "marketAreaResponsible": {
                "data": {"type": "luMarket", "id": "1", "meta": {"displayValue": "Test Region"}},
                "links": {"related": "/api/v0/riskAssessments/luMarket/1"}
            },
            "luPeopleAtRisk": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luPeopleAtRisk"}},
            "mtmGenericAssessment": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/mtmGenericAssessment"}},
            "employees": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/employees"}},
            "luFreelancers": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luFreelancers"}},
            "luDirectorate": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luDirectorate"}},
            "luLocationOfRisks": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luLocationOfRisks"}},
            "luOnSiteBuilding": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luOnSiteBuilding"}},
            "luHighRiskType": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luHighRiskType"}},
            "luLocationsRa": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luLocationsRa"}},
            "luLessonsIdentified": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/luLessonsIdentified"}},
            "sys_calculations": {"links": {"related": "/api/v0/riskAssessments/riskAssessment/80002/sys_calculations"}}
        },
        "links": {"self": "/api/v0/riskAssessments/riskAssessment/80002"}
    },
]

RISK_ASSESSMENT_TOTAL_COUNT = 1777  # fictional total, deliberately different from real prod count


# ------------------------------------------------------------------
# Sample data - rebuilt from the REAL field structure of an
# incidentReporting/injuredPerson record (confirmed against an actual
# prod sample), with entirely fictional values. All names, emails, and
# reference numbers below are fictional. Field names preserved exactly,
# including the array-valued relationships (bodyMap, luInjuriesSustained)
# which carry their own meta.totalCount - a pattern not present on the
# other 3 endpoints.
# ------------------------------------------------------------------
INJURED_PERSON_DATA = [
    {
        "id": "90001",
        "type": "injuredPerson",
        "attributes": {
            "injuredPersonRefNo": 5501,
            "dateCreated": "2026-01-06T00:00:00",
            "injuredPersonName": "Sample Injured Person One",
            "injuredPersonEmailAddress": "sample.injured.one@example-corp.test",
            "injuredPersonJobTitle": None,
            "injuredPersonPhoneNumber": None,
            "employerContactDetails": None,
            "shiftStartTime": "2000-01-01T08:00:00",
            "treatmentDetails": None,
            "whatWasTheNameOfTheHospital": None,
            "firstDayOfLostTime": "2026-01-05T00:00:00",
            "lastDayOfLostTime": "2026-01-07T00:00:00",
            "lastUpdatedOn": "2026-01-06T16:33:08",
            "lastUpdatedBy": "Sample Reviewer One",
            "employerName": None,
            "calculatedDaysOff": 2
        },
        "relationships": {
            "typeOfPerson": {
                "data": {"type": "luTypeOfPerson", "id": "1", "meta": {"displayValue": "Employee"}},
                "links": {"related": "/api/v0/incidentReporting/luTypeOfPerson/1"}
            },
            "employeeName": {
                "data": {"type": "employees", "id": "88801", "meta": {"displayValue": "Sample Injured Person One"}},
                "links": {"related": "/api/v0/incidentReporting/employees/88801"}
            },
            "gender": {
                "data": {"type": "luGender", "id": "1", "meta": {"displayValue": "Male"}},
                "links": {"related": "/api/v0/incidentReporting/luGender/1"}
            },
            "whatTreatmentWasProvided": {
                "data": {"type": "luTreatmentProvided", "id": "1", "meta": {"displayValue": "No Treatment"}},
                "links": {"related": "/api/v0/incidentReporting/luTreatmentProvided/1"}
            },
            "wasThisPersonPlacedOnRestrictedOrLight": {"data": None},
            "thisALostTimeInjury": {
                "data": {"type": "luYesNoUnknown", "id": "1", "meta": {"displayValue": "Yes"}},
                "links": {"related": "/api/v0/incidentReporting/luYesNoUnknown/1"}
            },
            "bodyMap": {
                "data": [{"type": "sys_imageHotSpots", "id": "60001"}],
                "links": {"related": "/api/v0/incidentReporting/injuredPerson/90001/sys_imageHotSpots/bodyMap"},
                "meta": {"totalCount": 1}
            },
            "doesThisIncidentNeedReportingToTheHse": {
                "data": {"type": "luYesNoUnknown", "id": "2", "meta": {"displayValue": "No"}},
                "links": {"related": "/api/v0/incidentReporting/luYesNoUnknown/2"}
            },
            "luInjuriesSustained": {
                "data": [{"type": "luInjuriesSustained", "id": "1", "meta": {"displayValue": "Strain/Sprain - Back"}}],
                "links": {"related": "/api/v0/incidentReporting/injuredPerson/90001/luInjuriesSustained"},
                "meta": {"totalCount": 1}
            },
            "sys_calculations": {
                "links": {"related": "/api/v0/incidentReporting/injuredPerson/90001/sys_calculations"}
            }
        },
        "links": {"self": "/api/v0/incidentReporting/injuredPerson/90001"}
    },
    {
        "id": "90002",
        "type": "injuredPerson",
        "attributes": {
            "injuredPersonRefNo": 5502,
            "dateCreated": "2026-02-11T00:00:00",
            "injuredPersonName": "Sample Injured Person Two",
            "injuredPersonEmailAddress": "sample.injured.two@example-corp.test",
            "injuredPersonJobTitle": None,
            "injuredPersonPhoneNumber": None,
            "employerContactDetails": None,
            "shiftStartTime": "2000-01-01T09:00:00",
            "treatmentDetails": "Sample fictional treatment note: minor first aid applied on site.",
            "whatWasTheNameOfTheHospital": None,
            "firstDayOfLostTime": None,
            "lastDayOfLostTime": None,
            "lastUpdatedOn": "2026-02-12T10:15:00",
            "lastUpdatedBy": "Sample Reviewer Two",
            "employerName": None,
            "calculatedDaysOff": 0
        },
        "relationships": {
            "typeOfPerson": {
                "data": {"type": "luTypeOfPerson", "id": "2", "meta": {"displayValue": "Contractor"}},
                "links": {"related": "/api/v0/incidentReporting/luTypeOfPerson/2"}
            },
            "employeeName": {"data": None},
            "gender": {
                "data": {"type": "luGender", "id": "2", "meta": {"displayValue": "Female"}},
                "links": {"related": "/api/v0/incidentReporting/luGender/2"}
            },
            "whatTreatmentWasProvided": {
                "data": {"type": "luTreatmentProvided", "id": "2", "meta": {"displayValue": "First Aid"}},
                "links": {"related": "/api/v0/incidentReporting/luTreatmentProvided/2"}
            },
            "wasThisPersonPlacedOnRestrictedOrLight": {"data": None},
            "thisALostTimeInjury": {
                "data": {"type": "luYesNoUnknown", "id": "2", "meta": {"displayValue": "No"}},
                "links": {"related": "/api/v0/incidentReporting/luYesNoUnknown/2"}
            },
            "bodyMap": {
                "data": [],
                "links": {"related": "/api/v0/incidentReporting/injuredPerson/90002/sys_imageHotSpots/bodyMap"},
                "meta": {"totalCount": 0}
            },
            "doesThisIncidentNeedReportingToTheHse": {
                "data": {"type": "luYesNoUnknown", "id": "2", "meta": {"displayValue": "No"}},
                "links": {"related": "/api/v0/incidentReporting/luYesNoUnknown/2"}
            },
            "luInjuriesSustained": {
                "data": [{"type": "luInjuriesSustained", "id": "2", "meta": {"displayValue": "Minor Cut/Abrasion"}}],
                "links": {"related": "/api/v0/incidentReporting/injuredPerson/90002/luInjuriesSustained"},
                "meta": {"totalCount": 1}
            },
            "sys_calculations": {
                "links": {"related": "/api/v0/incidentReporting/injuredPerson/90002/sys_calculations"}
            }
        },
        "links": {"self": "/api/v0/incidentReporting/injuredPerson/90002"}
    },
]

INJURED_PERSON_TOTAL_COUNT = 2441  # fictional total, deliberately different from any real prod count


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "mock-shield-api"}), 200, get_standard_headers()


@app.route('/identity/connect/token', methods=['POST'])
def get_token():
    """
    Mock OAuth2 client_credentials token endpoint.
    Accepts any client_id/client_secret - this mock does not validate
    credentials, it only tests the pipeline's request/response handling.
    """
    grant_type = request.form.get('grant_type')
    if grant_type != 'client_credentials':
        return jsonify({"error": "unsupported_grant_type"}), 400, get_standard_headers()

    return jsonify({
        "access_token": "MOCK-ACCESS-TOKEN-FOR-TESTING",
        "expires_in": 86400,
        "token_type": "Bearer",
    }), 200, get_standard_headers()


@app.route('/api/v0/riskAssessments/identifiedRisk', methods=['GET'])
def get_identified_risk():
    """
    Mock endpoint mimicking InfoExchange (Shield) JSON:API dynamic endpoint
    for the riskAssessments/identifiedRisk table.

    Query parameters supported:
        page[limit]  - max records to return (default 3, capped at sample size)
        page[offset] - offset into the sample set (wraps if beyond sample size)
    """
    # Basic bearer token presence check (does not validate the token value)
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({
            "errors": [{"detail": "Missing or invalid Authorization header"}]
        }), 401, get_standard_headers()

    try:
        limit = int(request.args.get('page[limit]', 3))
    except (TypeError, ValueError):
        limit = 3

    try:
        offset = int(request.args.get('page[offset]', 0))
    except (TypeError, ValueError):
        offset = 0

    # Serve from the small fixed sample set, cycling if offset exceeds it -
    # good enough for pipeline logic testing without needing 20k+ fake rows.
    start = offset % len(IDENTIFIED_RISK_DATA)
    records = (IDENTIFIED_RISK_DATA * 2)[start:start + limit]

    next_offset = offset + limit
    last_offset = IDENTIFIED_RISK_TOTAL_COUNT - limit

    response_body = {
        "data": records,
        "meta": {"totalCount": IDENTIFIED_RISK_TOTAL_COUNT},
        "links": {
            "next": f"/api/v0/riskAssessments/identifiedRisk?page%5Blimit%5D={limit}&page%5Boffset%5D={next_offset}",
            "last": f"/api/v0/riskAssessments/identifiedRisk?page%5Blimit%5D={limit}&page%5Boffset%5D={last_offset}",
        },
    }

    return jsonify(response_body), 200, get_standard_headers()


@app.route('/api/v0/incidentReporting/incidents', methods=['GET'])
def get_incidents():
    """
    Mock endpoint mimicking InfoExchange (Shield) JSON:API dynamic endpoint
    for the incidentReporting/incidents table.

    Query parameters supported:
        page[limit]  - max records to return (default 3, capped at sample size)
        page[offset] - offset into the sample set (wraps if beyond sample size)
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({
            "errors": [{"detail": "Missing or invalid Authorization header"}]
        }), 401, get_standard_headers()

    try:
        limit = int(request.args.get('page[limit]', 3))
    except (TypeError, ValueError):
        limit = 3

    try:
        offset = int(request.args.get('page[offset]', 0))
    except (TypeError, ValueError):
        offset = 0

    start = offset % len(INCIDENTS_DATA)
    records = (INCIDENTS_DATA * 2)[start:start + limit]

    next_offset = offset + limit
    last_offset = INCIDENTS_TOTAL_COUNT - limit

    response_body = {
        "data": records,
        "meta": {"totalCount": INCIDENTS_TOTAL_COUNT},
        "links": {
            "next": f"/api/v0/incidentReporting/incidents?page%5Blimit%5D={limit}&page%5Boffset%5D={next_offset}",
            "last": f"/api/v0/incidentReporting/incidents?page%5Blimit%5D={limit}&page%5Boffset%5D={last_offset}",
        },
    }

    return jsonify(response_body), 200, get_standard_headers()


@app.route('/api/v0/riskAssessments/riskAssessment', methods=['GET'])
def get_risk_assessment():
    """
    Mock endpoint mimicking InfoExchange (Shield) JSON:API dynamic endpoint
    for the riskAssessments/riskAssessment table.

    Query parameters supported:
        page[limit]  - max records to return (default 3, capped at sample size)
        page[offset] - offset into the sample set (wraps if beyond sample size)
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({
            "errors": [{"detail": "Missing or invalid Authorization header"}]
        }), 401, get_standard_headers()

    try:
        limit = int(request.args.get('page[limit]', 3))
    except (TypeError, ValueError):
        limit = 3

    try:
        offset = int(request.args.get('page[offset]', 0))
    except (TypeError, ValueError):
        offset = 0

    start = offset % len(RISK_ASSESSMENT_DATA)
    records = (RISK_ASSESSMENT_DATA * 2)[start:start + limit]

    next_offset = offset + limit
    last_offset = RISK_ASSESSMENT_TOTAL_COUNT - limit

    response_body = {
        "data": records,
        "meta": {"totalCount": RISK_ASSESSMENT_TOTAL_COUNT},
        "links": {
            "next": f"/api/v0/riskAssessments/riskAssessment?page%5Blimit%5D={limit}&page%5Boffset%5D={next_offset}",
            "last": f"/api/v0/riskAssessments/riskAssessment?page%5Blimit%5D={limit}&page%5Boffset%5D={last_offset}",
        },
    }

    return jsonify(response_body), 200, get_standard_headers()


@app.route('/api/v0/incidentReporting/injuredPerson', methods=['GET'])
def get_injured_person():
    """
    Mock endpoint mimicking InfoExchange (Shield) JSON:API dynamic endpoint
    for the incidentReporting/injuredPerson table.

    Query parameters supported:
        page[limit]  - max records to return (default 3, capped at sample size)
        page[offset] - offset into the sample set (wraps if beyond sample size)
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({
            "errors": [{"detail": "Missing or invalid Authorization header"}]
        }), 401, get_standard_headers()

    try:
        limit = int(request.args.get('page[limit]', 3))
    except (TypeError, ValueError):
        limit = 3

    try:
        offset = int(request.args.get('page[offset]', 0))
    except (TypeError, ValueError):
        offset = 0

    start = offset % len(INJURED_PERSON_DATA)
    records = (INJURED_PERSON_DATA * 2)[start:start + limit]

    next_offset = offset + limit
    last_offset = INJURED_PERSON_TOTAL_COUNT - limit

    response_body = {
        "data": records,
        "meta": {"totalCount": INJURED_PERSON_TOTAL_COUNT},
        "links": {
            "next": f"/api/v0/incidentReporting/injuredPerson?page%5Blimit%5D={limit}&page%5Boffset%5D={next_offset}",
            "last": f"/api/v0/incidentReporting/injuredPerson?page%5Blimit%5D={limit}&page%5Boffset%5D={last_offset}",
        },
    }

    return jsonify(response_body), 200, get_standard_headers()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
