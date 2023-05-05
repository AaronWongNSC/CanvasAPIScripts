'''
last_nonzero_score.py

Description: This script estimates the date of last participation of students
in a class by determining the date of the last non-zero score on some assignment.
It uses the Canvas API, which requires that the faculty member has generated an API token.

Requirements:
    * Faculty must create an API token (instructions below)
    * Assignments must generally have a due date (assignments without a due date will not be counted)

General advice:
    * This script works best if students are regularly graded on something
    --- For example, attendance, discussions, or daily/weekly quizzes

API Key:
    * NOTE: Access to API keys may vary from institution to institution.
    * WARNING: Treat your API key like a password. Anyone with your key basically
        has access to your entire Canvas account.
    * To obtain a key:
    --- Log into Canvas
    --- Click your profile image (typically at the top-left)
    --- Select "Settings"
    --- Scroll down to "Approved Integrations" and scroll to the bottom of that section
    --- Click the "+Add Access Token"
    --- For "Purpose" type anything you want, such as "Last Nonzero Grade"
    --- For the expiration date, pick a date about one week in the future [Note: This is for
        security purposes. You can always generate new tokens later.]
    --- Click "Generate Token"
    --- Copy the long string of text between the quotes in the line below that says API_KEY = ""

Course ID: The class number can be determined in Canvas by going to the main course page and
reading the URL. You should see something like https://instructure.com/courses/<number>. You just
need to copy the number after the equal sign in the line below that says COURSE_ID = 0
'''

# User-Specific Information --- Update this section!
INSTITUTION_URL = 'https://nsc.instructure.com' # No / at end
API_KEY = "" # See above
COURSE_ID = 0 # See above


##### BEGIN SCRIPT #####

import requests
from datetime import datetime

# Helper Functions
def get_navigation(link_list):
    current_link = ''
    next_link = ''
    last_link = ''
    for link_info in link_list:
        if 'rel="current"' in link_info:
            current_link = link_info.split(';')[0].strip('<>')
        if 'rel="next"' in link_info:
            next_link = link_info.split(';')[0].strip('<>')
        if 'rel="last"' in link_info:
            last_link = link_info.split(';')[0].strip('<>')
    return current_link, next_link, last_link

def get_list(session, headers, first_url):
    this_list = []
    url = first_url
    while True:
        response = session.get(url, headers = headers)
        current_link, next_link, last_link = get_navigation(response.headers['link'].split(','))
        this_list = this_list + response.json()

        if current_link == last_link:
            break
        url = next_link
    return this_list
    
def z_to_dt(z):
    if z == None:
        return 
    return datetime.strptime(z, '%Y-%m-%dT%H:%M:%SZ')

def dt_to_z(dto):
    if dto == None:
        return 
    return dto.strftime('%Y-%m-%dT%H:%M:%SZ')

# Setup API
API_URL = INSTITUTION_URL + "/api/v1"
auth = {"Authorization": "Bearer {}".format(API_KEY)}
session = requests.Session()

# Get assignment groups
print('Getting assignment groups...')
url = API_URL + '/courses/{}/assignment_groups?per_page=100'.format(COURSE_ID)
assignment_groups = get_list(session, auth, url)
assignment_groups = { assignment_group['id']: assignment_group for assignment_group in assignment_groups}

# Get assignments
print('Getting assignments...')
url = API_URL + '/courses/{}/assignments?per_page=100'.format(COURSE_ID)
assignments = get_list(session, auth, url)
assignments = { assignment['id']: assignment for assignment in assignments }

assignments_by_group_id = { assignment_group_id: [] for assignment_group_id in assignment_groups}
for assignment_id in assignments:    
    assignments_by_group_id[ assignments[assignment_id]['assignment_group_id'] ].append(assignment_id)

# Get active students
print('Getting active students...')
url = API_URL + '/courses/{}/enrollments?type[]=StudentEnrollment&state[]=active&per_page=100'.format(COURSE_ID)
students = get_list(session, auth, url)
students = { str(student['user_id']): student for student in students }

# Get submissions by assignment
print('Getting submissions...')
all_submissions = {}
for count, assignment_id in enumerate(assignments):
    print('{} of {} -- {}'.format(count + 1, len(assignments), assignment_id))
    url = API_URL + '/courses/{}/assignments/{}/submissions?per_page=100'.format(COURSE_ID, assignment_id)
    submissions = get_list(session, auth, url)
    all_submissions.update({assignment_id: submissions})

# Sort the assignments by date
print('Sorting Assignments')

due_dates = [ z_to_dt(assignments[assignment]['due_at']) for assignment in assignments ]
due_dates = list(set([ date for date in due_dates if date is not None]))
due_dates.sort()
due_dates.append(None)

assignment_ids_by_due_date = [ assignment_id
                           for date in due_dates
                           for assignment_id in assignments
                           if z_to_dt(assignments[assignment_id]['due_at']) == date]

## Determine last nonzero score
print('Determining Last Nonzero Score...')

first_due_date = z_to_dt(assignments[assignment_ids_by_due_date[0]]['due_at'])
last_non_zero_score = { student_id: first_due_date for student_id in students }

for assignment_id in assignment_ids_by_due_date:
    for submission in all_submissions[assignment_id]:
        if type(submission['score']) != float:
            continue
        assignment_date = z_to_dt(assignments[assignment_id]['due_at'])
        if assignment_date is None:
            continue
        student_id = str(submission['user_id'])
        if student_id not in students:
            continue
        if submission['score'] > 0 and assignment_date > last_non_zero_score[student_id]:
            last_non_zero_score[student_id] = assignment_date

## Determine last submission
print('Determining Last Submission...')

last_submission = { student_id: None for student_id in students }

for submission_id in all_submissions:
    for submission in all_submissions[submission_id]:
        student_id = str(submission['user_id'])
        submitted_at = z_to_dt(submission['submitted_at'])
        if submitted_at is None:
            continue
        if student_id not in students:
            continue

        if last_submission[student_id] == None:
            last_submission[student_id] = submitted_at
            continue
        if submitted_at > last_submission[student_id]:
            last_submission[student_id] = submitted_at

# Export File
print('Exporting CSV...')
now = datetime.now().strftime('%Y-%m-%d-%H%M')

with open('{}-LastParticipation-{}.csv'.format(now, COURSE_ID), 'w') as outfile:
    outfile.write('Student,ID,Last Nonzero Assignment Due Date,Last Submission\n')
    for student_id in students:
        outfile.write('"{}",{},{},{}\n'.format(
            students[student_id]['user']['sortable_name'],
            students[student_id]['user']['sis_user_id'],
            last_non_zero_score[student_id],
            last_submission[student_id]))
    
    print('Success!')
