import requests
import re
import pandas as pd
from bs4 import BeautifulSoup

DEPTS = ['MATH', 'COGS', 'ECE', 'CSE']

# NOTE: Intentionally ignored case where a course has different credit options
RE_COURSE_TITLE_PARSER = '([A-Z]+) (\d+[A-Z]*)\. (\S.+) \((\d+)\)'
RE_PREREQ_PARSER = 'Prerequisites:(.+).'
#RE_COUNT_PREREQ_PARSER = "\d+\w+"
RE_COUNT_PREREQ_PARSER = "\d+\w+|\d+"

def parse_prereq(prereq_str):
    """
    Parses prerequisite string into list of courses
    """
    # TODO: Fix distinguishing things like MATH 31AH (which is right) and COGS 14AB (which is wrong)
    punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~'''
    strings_to_remove = ["PNP", "P/NP", "GPA", "May", "Recommend", "Cognitive Science Honors Program"]

    for x in strings_to_remove:
        prereq_str = prereq_str.replace(x, "")

    for x in prereq_str:
        if x in punctuations or x.islower():
            prereq_str = prereq_str.replace(x, "")

    prereq_list = []
    prereq_index_list = [0]

    for i in range(1, len(prereq_str)):
        if prereq_str[i].isalpha() and prereq_str[i - 1] == " ":
            prereq_index_list.append(i)

    for i in range(len(prereq_index_list)):

        if i == len(prereq_index_list) - 1:
            prereq = prereq_str[prereq_index_list[i]:].rstrip()
        else:
            prereq = prereq_str[prereq_index_list[i]: prereq_index_list[i + 1]].rstrip()

        if len(prereq) >= 4:
            prereq_list.append(prereq)

    prereq_str = prereq_list

    return prereq_str

def count_prereq(prereq_list):
    """
    Count courses taken as prerequisites.
    Ex. COGS 108 takes CSE 11, CSE 8A, COGS 18, DSC 10, MAE 8 as prerequisites (ignoring and/or),
        so count_prereq for COGS 108 is 5.
    """
    prereq_count = 0

    for i in range(len(prereq_list)):
        prereq_count += len(re.findall(RE_COUNT_PREREQ_PARSER, prereq_list[i]))

    return prereq_count

def count_prereqed(prereqed_list, target_course):
    """
    Count courses that take target_course as a prerequisite.
    Ex. COGS 118A, COGS 118C, COGS 180, COGS 189 take COGS 108 as a prerequisite (ignoring and/or),
        so count_prereqed for COGS 108 is 4.
    """
    prereqed_count = 0

    try:
        for i in range(len(prereqed_list)):
            for j in range(len(prereqed_list[i])):
                if prereqed_list[i][j] == target_course:
                    prereqed_count += 1
    except:
        # print("Error in count_prereqed")
        pass

    return prereqed_count

def get_dept_catalog(dept, verbose=False):
    # assert dept in DEPTS, f'Cannot get dept {dept}, only support {DEPTS}!'
    url = f"https://www.ucsd.edu/catalog/courses/{dept}.html"
    page = requests.get(url)

    # assert page.status_code == 200, f'Error loading {url}! Internet?'
    if page.status_code == 200:
        soup = BeautifulSoup(page.content, 'html.parser')
        catalog_dict = dict()
        # Extract course entries from HTML
        for course_title in soup.find_all('p', class_='course-name'):
            next_sibling = course_title.find_next_sibling('p', class_='course-descriptions')
            if next_sibling != None:
                catalog_dict[course_title.getText()] = next_sibling.getText()

        # Parsing ...
        output_list = list()
        unable_parse = list()

        for course_title, course_descrip in catalog_dict.items():
            this_course = dict()
            # Parse title
            course_title = course_title.replace('\n', '').replace('\t', '').replace(u'\xa0', u' ')
            parsed = re.findall(RE_COURSE_TITLE_PARSER, course_title)
            if len(parsed) == 1 and len(parsed[0]) == 4:
                cdept, cid, cdesc, ccred = parsed[0]
                this_course = {'dept': cdept, 'num': cid, 'desc': cdesc, 'cred': ccred, 'prereq': []}
            else:
                if verbose:
                    print(f"Warning: Ignored ->{course_title}<- Unable to parse.")
                unable_parse.append(course_title)
                continue

            # Parse prerequisite
            course_descrip = course_descrip.replace('\n', '').replace('\t', '').replace(u'\xa0', u' ')
            course_descrip = course_descrip.replace('/\s\s+/g', ' ');
            prerequisites = []
            if 'Prerequisites' in course_descrip:
                prereq_str = re.findall(RE_PREREQ_PARSER, course_descrip)

                if len(prereq_str) != 1:
                    print(course_title)
                    print(course_descrip)

                assert len(prereq_str) == 1
                prerequisites.append(prereq_str[0])
                this_course['prereq'] = parse_prereq(prereq_str[0])
            output_list.append(this_course)

        # Construct df from output
        cat_df = pd.DataFrame(output_list)
        # Filter out courses > 189 after filtering out letters from course id
        cat_df = cat_df[cat_df['num'].apply(lambda course_id: re.sub("[^0-9]+", "", course_id)).apply(int) <= 189]
        cat_df['course'] = cat_df['dept'] + ' ' + cat_df['num']

        cat_df['prereq_count'] = cat_df['prereq'].apply(count_prereq)

        for i in range(len(cat_df.index)):
            cat_df.at[i, "prereqed_count"] = count_prereqed(cat_df['prereq'].tolist(), cat_df.iloc[i]['course'])

        return cat_df

    else:
        return None

def merge_catalog_to_cape(catalog_df, cape_df):
    return catalog_df.merge(cape_df, how='inner', on='course')
