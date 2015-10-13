#! /usr/bin/env python

import requests
import fnmatch
import subprocess
import argparse
import json


def get_header_string():
    buf = '''AUTOMATIC LINT RESULTS DO NOT EDIT\n'''
    return buf


def get_lint_comment(base, api_key, pr_num):
    url = base + '/issues/{num}/comments?access_token={api_key}'.format(num=pr_num,
                                                                       api_key=api_key)
    headers = {}
    headers['Accept'] = 'application/json'
    comment_id = None
    req = requests.get(url, headers=headers)
    for comment in req.json():
        if comment['body'].startswith(get_header_string()):
            comment_id = comment['id']
    return comment_id


def create_or_update_lint_comment(base, api_key, pr_num, errors):
    body = get_header_string() + '\n' + generate_buf(errors)
    comment_id = get_lint_comment(base, api_key, pr_num)
    data = {'body': body}
    if comment_id:
        url = base + '/issues/comments/{id}?access_token={api_key}'.format(num=pr_num,
                                                                                 id=comment_id,
                                                                                 api_key=api_key)
        requests.patch(url, headers=get_headers(), data=json.dumps(data))
    else:
        url = base + '/issues/{num}/comments?access_token={api_key}'.format(num=pr_num,
                                                                            api_key=api_key)
        requests.post(url, headers=get_headers(), data=json.dumps(data))

def get_headers():
    return {'Accept': 'application/json'}

def post_result(base, failed_files, api_key, sha):
    url = base + '/statuses/{sha}?access_token={api_key}'.format(sha=sha,
                                                                 api_key=api_key)
    if any(failed_files):
        status = 'failure'
        description = 'Lint failed'
        # Sad Panda
        link = 'http://fc08.deviantart.net/fs70/f/2010/149/a/7/Sad_Panda_Chibi_by_mongrelssister.png'
    else:
        status = 'success'
        description = 'Lint passed'
        link = 'http://i.imgur.com/DPVM1.png'
    data = {"state": status, "target_url": link,
            "description": description, "context": "lint"}
    headers = {}
    headers['Accept'] = 'application/json'
    requests.post(url, data=json.dumps(data), headers=headers)


def generate_buf(errors):
    if errors:
        msg = []
        for fname, errors in errors.iteritems():
            msg += ['Lint Errors for {}'.format(fname)]
            for error in errors:
                line_num, errstr = error
                msg.append('\t{}:\t{}'.format(line_num, errstr))
        msg = '\n'.join(msg)
    else:
        msg = 'Lint all good :shipit:'
    return msg

def post_errors(errors, base, api_key, sha):
    url = base + '/commits/{sha}/comments?access_token={api_key}'.format(sha=sha,
                                                                         api_key=api_key)
    for fname, errors in errors.iteritems():
        msg = generate_buf(errors)
        data = {'body': msg,
                'path': fname,
                'position': 1,
                'line': None}
        headers = {}
        headers['Accept'] = 'application/json'
        requests.post(url, data=json.dumps(data), headers=headers)


def get_errors(lint_output):
    errors = {}
    for line in lint_output:
        if line:
            #  lib/deepy/jobs_daemon.py:7: 'foo' imported but unused
            fname, num, errstr = line.split(':')
            errors.setdefault(fname, [])
            errors[fname].append((num, errstr))
    return errors


def run_lint(path, files, lint='pyflakes', pattern='*.py'):
    failed = []
    output = []
    for fname in files:
        if not fnmatch.fnmatch(fname, pattern):
            continue
        try:
            subprocess.check_output([lint + " " + fname], shell=True, cwd=path)
        except subprocess.CalledProcessError as e:
            output += e.output.split('\n')
            failed.append(fname)
    return failed, output


def get_changed_files(api_key, repo_base, pr_num):
    '''
    Retrieve the list of changed files for a pull request
    '''
    "https://api.github.com/repos/deepfield/pipedream/statuses/$bamboo_pull_sha?access_token={api_key}"
    url = repo_base + "/pulls/{num}/files?access_token={api_key}".format(num=pr_num, api_key=api_key)
    req = requests.get(url)
    data = req.json()
    files = [v['filename'] for v in data]
    return files


def parse_args():
    p = argparse.ArgumentParser(description='''
    Get changed files from a pull-request and check for lint errors
    ''')
    p.add_argument('--pr-num', help='pull-request num', required=True)
    p.add_argument('--repo-base', help='repo-base-url', required=True)
    p.add_argument('--path', help='path to repo', required=True)
    p.add_argument('--gh-api-write', help='gh api key used to post comments/status', required=True)
    p.add_argument('--gh-api-read', help='gh api key used to read changed files (defaults to write if not specified)')
    p.add_argument('--sha', help='commit hash', required=True)
    return p.parse_args()


def main():
    args = parse_args()
    write_key = args.gh_api_write
    if args.gh_api_read:
        read_key = args.gh_api_read
    else:
        read_key = args.gh_api_write
    files = get_changed_files(read_key, args.repo_base, args.pr_num)
    failed, errors = run_lint(args.path, files)
    errors = get_errors(errors)
    create_or_update_lint_comment(args.repo_base, read_key,
                                  args.pr_num, errors)
    post_result(args.repo_base, failed, write_key, args.sha)

if __name__ == '__main__':
    main()
