# Run comparison
31 change(s) across 7 patient(s).

## Kintu-Test 001
- runs: 3 before, 3 after
- **status: changed** ['YELLOW', 'YELLOW', 'YELLOW'] -> ['YELLOW', 'RED', 'YELLOW']
- **alerts: changed** [3, 2, 3] -> [3, 6, 6]
- **rule alerts: changed** [0, 0, 0] -> [1, 1, 1]
- **rule alerts kept on screen: changed** [0, 0, 0] -> [1, 1, 1]
- plan items: same ([3, 3, 3])
- **plan items with no model verdict: changed** [3, 3, 3] -> [0, 0, 0]
- llm error: same ([False, False, False])
- **retrieved passages by document: changed** ['HIV_Guidelines_ART.extraction.md 7, HIV_Guidelines_Co_infectionScreening.extraction.md 2, SAHCS_Adult_ART_2024.md 5, WHO_guidelines.extraction.md 1', 'HIV_Guidelines_ART.extraction.md 4, HIV_Guidelines_Co_infectionScreening.extraction.md 3, SAHCS_Adult_ART_2024.md 3', 'HIV_Guidelines_ART.extraction.md 8, HIV_Guidelines_Co_infectionScreening.extraction.md 1, SAHCS_Adult_ART_2024.md 5, WHO_guidelines.extraction.md 1'] -> ['HIV_Guidelines_ART.extraction.md 4, HIV_Guidelines_Co_infectionScreening.extraction.md 1, SAHCS_Adult_ART_2024.md 2', 'HIV_Guidelines_ART.extraction.md 4, HIV_Guidelines_Co_infectionScreening.extraction.md 1, SAHCS_Adult_ART_2024.md 2', 'HIV_Guidelines_ART.extraction.md 4, HIV_Guidelines_Co_infectionScreening.extraction.md 1, SAHCS_Adult_ART_2024.md 2']
- alert titles gone: ['Missing Monitoring Data', 'Monitoring Gap for Lipid Profile']
- alert titles new: ['Blood Pressure Elevation', 'Creatinine recorded only as pasted text', 'Glucose Monitoring', 'Lipid Profile', 'Missing Assessment and Plan']

## P001
- runs: 3 before, 3 after
- status: same (['YELLOW', 'YELLOW', 'YELLOW'])
- alerts: same ([3, 3, 3])
- rule alerts: same ([1, 1, 1])
- **rule alerts kept on screen: changed** [0, 0, 0] -> [1, 1, 1]
- plan items: same ([2, 2, 2])
- plan items with no model verdict: same ([0, 0, 0])
- llm error: same ([False, False, False])
- **retrieved passages by document: changed** ['HIV_Guidelines_ART.extraction.md 12, HIV_Guidelines_Co_infectionScreening.extraction.md 1, SAHCS_Adult_ART_2024.md 2', 'HIV_Guidelines_ART.extraction.md 12, SAHCS_Adult_ART_2024.md 3', 'HIV_Guidelines_ART.extraction.md 9, HIV_Guidelines_Co_infectionScreening.extraction.md 1, SAHCS_Adult_ART_2024.md 5'] -> ['SAHCS_Adult_ART_2024.md 6', 'SAHCS_Adult_ART_2024.md 6', 'SAHCS_Adult_ART_2024.md 6']
- alert titles gone: ['Adherence and Side Effects Monitoring', 'Incomplete Medication History', 'Lack of Adherence Support Plan', 'Missing Creatinine Trend', 'Missing Creatinine Trend Monitoring', 'Missing Viral Load Monitoring', 'Neuropsychiatric Symptom Screening']
- alert titles new: ['Creatinine monitoring overdue while on TDF', 'Inadequate Virological Monitoring', 'Missing Recent Creatinine']

## P002
- runs: 3 before, 3 after
- status: same (['YELLOW', 'YELLOW', 'YELLOW'])
- **alerts: changed** [5, 3, 3] -> [2, 2, 2]
- rule alerts: same ([0, 0, 0])
- rule alerts kept on screen: same ([0, 0, 0])
- plan items: same ([2, 2, 2])
- **plan items with no model verdict: changed** [2, 2, 2] -> [0, 0, 0]
- llm error: same ([False, False, False])
- **retrieved passages by document: changed** ['HIV_Guidelines_ART.extraction.md 20, HIV_Guidelines_Co_infectionScreening.extraction.md 2, SAHCS_Adult_ART_2024.md 3', 'HIV_Guidelines_ART.extraction.md 12, HIV_Guidelines_Co_infectionScreening.extraction.md 1, SAHCS_Adult_ART_2024.md 2', 'HIV_Guidelines_ART.extraction.md 11, HIV_Guidelines_Co_infectionScreening.extraction.md 2, SAHCS_Adult_ART_2024.md 2'] -> ['HIV_Guidelines_ART.extraction.md 1, SAHCS_Adult_ART_2024.md 1', 'HIV_Guidelines_ART.extraction.md 1, SAHCS_Adult_ART_2024.md 1', 'HIV_Guidelines_ART.extraction.md 1, SAHCS_Adult_ART_2024.md 1']
- alert titles gone: ['Inadequate Adherence Support', 'Inadequate Viral Load Monitoring', 'Incomplete Patient History', 'Lack of Adherence Support', 'Lack of Adverse Drug Reaction Screening', 'Missing Laboratory Results', 'No Current Clinician Plan']
- alert titles new: ['Creatinine Monitoring', 'Viral Load Monitoring']

## P003
- runs: 3 before, 3 after
- status: same (['YELLOW', 'YELLOW', 'YELLOW'])
- **alerts: changed** [3, 3, 3] -> [3, 4, 4]
- rule alerts: same ([2, 2, 2])
- **rule alerts kept on screen: changed** [0, 0, 0] -> [2, 2, 2]
- plan items: same ([2, 2, 2])
- **plan items with no model verdict: changed** [2, 2, 2] -> [0, 0, 0]
- llm error: same ([False, False, False])
- **retrieved passages by document: changed** ['HIV_Guidelines_ART.extraction.md 8, HIV_Guidelines_Co_infectionScreening.extraction.md 2, SAHCS_Adult_ART_2024.md 5', 'HIV_Guidelines_ART.extraction.md 8, HIV_Guidelines_Co_infectionScreening.extraction.md 3, SAHCS_Adult_ART_2024.md 4', 'HIV_Guidelines_ART.extraction.md 8, HIV_Guidelines_Co_infectionScreening.extraction.md 2, SAHCS_Adult_ART_2024.md 5'] -> ['HIV_Guidelines_ART.extraction.md 4, SAHCS_Adult_ART_2024.md 8', 'HIV_Guidelines_ART.extraction.md 4, SAHCS_Adult_ART_2024.md 9', 'HIV_Guidelines_ART.extraction.md 4, SAHCS_Adult_ART_2024.md 9']
- alert titles gone: ['Follow-up Assessment for Neuropsychiatric Symptoms', 'Lack of Clinician Plan', 'Missing Laboratory Results']
- alert titles new: ['Creatinine missing while on TDF', 'Mental Health Screening', 'Possible EFV neuropsychiatric side effects']

## P004
- runs: 3 before, 3 after
- **status: changed** ['YELLOW', 'RED', 'YELLOW'] -> ['YELLOW', 'YELLOW', 'YELLOW']
- alerts: same ([2, 2, 2])
- rule alerts: same ([0, 0, 0])
- rule alerts kept on screen: same ([0, 0, 0])
- **plan items: changed** [1, 1, 2] -> [3, 2, 2]
- **plan items with no model verdict: changed** [1, 1, 2] -> [0, 0, 0]
- llm error: same ([False, False, False])
- **retrieved passages by document: changed** ['HIV_Guidelines_ART.extraction.md 6, HIV_Guidelines_Co_infectionScreening.extraction.md 3, SAHCS_Adult_ART_2024.md 1', 'HIV_Guidelines_ART.extraction.md 7, HIV_Guidelines_Co_infectionScreening.extraction.md 2, SAHCS_Adult_ART_2024.md 1', 'HIV_Guidelines_ART.extraction.md 6, HIV_Guidelines_Co_infectionScreening.extraction.md 3, SAHCS_Adult_ART_2024.md 1'] -> ['HIV_Guidelines_ART.extraction.md 2', 'HIV_Guidelines_ART.extraction.md 2', 'HIV_Guidelines_ART.extraction.md 2']
- alert titles gone: ['Missing Laboratory Results']
- alert titles new: ['Missing Lab Results', 'Missing Recent Lab Results']

## P005
- runs: 3 before, 3 after
- status: same (['YELLOW', 'YELLOW', 'YELLOW'])
- **alerts: changed** [3, 3, 3] -> [8, 6, 6]
- **rule alerts: changed** [0, 0, 0] -> [3, 3, 3]
- **rule alerts kept on screen: changed** [0, 0, 0] -> [3, 3, 3]
- **plan items: changed** [2, 2, 3] -> [4, 2, 3]
- **plan items with no model verdict: changed** [2, 2, 3] -> [0, 0, 0]
- llm error: same ([False, False, False])
- **retrieved passages by document: changed** ['HIV_Guidelines_ART.extraction.md 4, SAHCS_Adult_ART_2024.md 9, WHO_guidelines.extraction.md 2', 'HIV_Guidelines_ART.extraction.md 7, SAHCS_Adult_ART_2024.md 7, WHO_guidelines.extraction.md 1', 'HIV_Guidelines_ART.extraction.md 12, HIV_Guidelines_Co_infectionScreening.extraction.md 1, SAHCS_Adult_ART_2024.md 2'] -> ['HIV_Guidelines_ART.extraction.md 4, SAHCS_Adult_ART_2024.md 15, WHO_guidelines.extraction.md 1', 'HIV_Guidelines_ART.extraction.md 4, SAHCS_Adult_ART_2024.md 13, WHO_guidelines.extraction.md 1', 'HIV_Guidelines_ART.extraction.md 4, SAHCS_Adult_ART_2024.md 12, WHO_guidelines.extraction.md 1']
- alert titles gone: ['Ibuprofen Use with TLD']
- alert titles new: ['Creatinine recorded only as pasted text', 'Lipid Monitoring Gap', 'Missing Assessment and Plan', 'Monitoring Gap', 'NSAID use mentioned while on TDF', 'Potential Ibuprofen Interaction', 'Proteinuria', 'Proteinuria mentioned in notes']

## P006
- runs: 3 before, 3 after
- status: same (['YELLOW', 'YELLOW', 'YELLOW'])
- **alerts: changed** [5, 5, 5] -> [4, 4, 4]
- **rule alerts: changed** [0, 0, 0] -> [1, 1, 1]
- **rule alerts kept on screen: changed** [0, 0, 0] -> [1, 1, 1]
- **plan items: changed** [2, 2, 2] -> [3, 3, 3]
- **plan items with no model verdict: changed** [0, 2, 2] -> [0, 0, 0]
- llm error: same ([False, False, False])
- **retrieved passages by document: changed** ['HIV_Guidelines_ART.extraction.md 13, SAHCS_Adult_ART_2024.md 10, WHO_guidelines.extraction.md 2', 'HIV_Guidelines_ART.extraction.md 17, HIV_Guidelines_Co_infectionScreening.extraction.md 1, SAHCS_Adult_ART_2024.md 5, WHO_guidelines.extraction.md 2', 'HIV_Guidelines_ART.extraction.md 17, HIV_Guidelines_Co_infectionScreening.extraction.md 1, SAHCS_Adult_ART_2024.md 6, WHO_guidelines.extraction.md 1'] -> ['HIV_Guidelines_ART.extraction.md 2, SAHCS_Adult_ART_2024.md 4, WHO_guidelines.extraction.md 1', 'HIV_Guidelines_ART.extraction.md 2, SAHCS_Adult_ART_2024.md 4, WHO_guidelines.extraction.md 1', 'HIV_Guidelines_ART.extraction.md 3, SAHCS_Adult_ART_2024.md 4, WHO_guidelines.extraction.md 1']
- alert titles gone: ['DTG-Based Regimen in Pregnancy', 'Elevated Creatinine', 'Iron Supplements and DTG Interaction', 'Missing Regimen History', 'Phosphate Level']
- alert titles new: ['Creatinine recorded only as pasted text']

