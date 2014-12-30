#!/usr/bin/env python
# Pull request validation checker
# Loads config to connect to various repos pull-requests comments and validate
#  based on different criteria.

import github3
import json
import re
import ConfigParser


class LeckPullChecker:
    config = ConfigParser.ConfigParser()
    gh = None
    repo = 'default'

    def __init__(self, configfile='config.ini', reponame=None):
        # Initialize connection from config
        self.config.read(configfile)
        self.repo = reponame if reponame else 'default'
        self.gh = github3.GitHubEnterprise(
            url=self.config.get('default', 'github'),
            token=self.config.get(self.repo, 'token'))

    def check(self, pullnumber=None):
        for section in self.config.sections():
            if section == 'default':
                continue
            # TODO Submit upstream helper for owner/repo shortname passing
            section_split = section.split('/')
            ownername = section_split[0]
            reponame = section_split[1]
            repo = self.gh.repository(ownername, reponame)
            # Run through tests pull-request acceptance
            if pullnumber is None:
                for pr in repo.iter_pulls(state='open'):
                    self.validate_pr(pr)
            else:
                self.validate_pr(repo.pull_request(pullnumber))
        return self

    def validate_pr(self, pr):
        review_comments = pr.iter_comments()
        issue_comments = pr.iter_issue_comments()

        # Validate
        self._validate_pr_initial_message(pr, issue_comments)
        self._validate_pr_title(pr, issue_comments)
        # Merge (if possible)
        self._validate_pr_merge(pr, issue_comments, review_comments)
        return self

    def _validate_pr_initial_message(self, pr, issue_comments):
        # TODO: consider breaking these out to loadable methods...
        hasinitmsg = False  # TODO: config.get help == True as well
        for ic in issue_comments:
            if 'Leck PR automation' in ic.body_text:
                hasinitmsg = True
                break
        if not hasinitmsg:
            self._pr_create_issue_comment(pr, '''### Leck PR automation

Reviews pull requests for matching criteria:

*  Sum of +2 from authorized reviewers (comment with "+1" or ":+1:", if authorized)
*  Merge comment from an authroized reviewer (comment with "merge", if authorized; to replace the merge button)
*  Summarize pull-request comments into the merge commit (for review in git history)

More info: [Leck](http://example.com/leckhelp)
''')

    def _validate_pr_title(self, pr, issue_comments):
        rtitle = re.compile(self.config.get(self.repo, 'title'))
        propertitle = rtitle.match(pr.title)

        hastitlemsg = False
        issueid = None
        for ic in issue_comments:
            if 'Title should be in the format' in ic.body_text:
                hastitlemsg = True
                issueid = ic.id
                break
        if not hastitlemsg and not propertitle:
            self._pr_create_issue_comment(pr, '''Title should be in the format: "[#PROJ-1234] Short description."''')
        if hastitlemsg and propertitle and (issueid == ic.id):
            # Remove existing comment if the title has been corrected
            ic.delete()

    def _pr_score(self, pr, issue_comments):
        # Returns true if comments add to > config required
        commentstotal = 0
        for ic in issue_comments:
            if '+1' in ic.body_text:
                commentstotal += 1
            if '-1' in ic.body_text:
                commentstotal -= 1
        return (commentstotal >= self.config.get(self.repo, 'required'))

    def _validate_pr_merge(self, pr, issue_comments, review_comments):
        if pr.mergeable and self._pr_score(pr, issue_comments):
            hasmergemsg = False
            issueid = None
            for ic in issue_comments:
                if 'merge' in ic.body_text:
                    hasmergemsg = True
                    issueid = ic.id
                    break
            if hasmergemsg and (issueid == ic.id):
                # Remove existing comment if the title has been corrected
                ic.delete()
                # TODO: Summarize PR into commit message
                # participants, merger, approvers, issue comments, review comments

    def _pr_create_issue_comment(self, pr, body):
        print pr.number
        print pr.repository
        print body
        print "^ in _pr_create_issue_comment"


    @staticmethod
    def create_pullcheck_from_hook(hook_type, data, config='config.ini'):
        gh = github.Github()
        reponame = None
        pullnumber = None

        js = json.loads(data)

        if (hook_type == 'pull_request'):
            repo = gh.create_from_raw_data(
                github.Repository.Repository,
                js['repository'])
            pr = gh.create_from_raw_data(
                github.PullRequest.PullRequest,
                js['pull_request'])
            reponame = repo.full_name
            pullnumber = pr.number
        elif (hook_type == 'issue_comment'):
            repo = gh.create_from_raw_data(
                github.Repository.Repository,
                js['repository'])
            issue = gh.create_from_raw_data(github.Issue.Issue, js['issue'])
            reponame = repo.full_name
            pullnumber = issue.number

        # Note if reponame and pullnumber are None - we should still dtrt (albeit not as targeted).
        lpc = LeckPullChecker(config, reponame)
        lpc.check(pullnumber)
        return lpc

if __name__ == '__main__':
    # Construct based on CLI args
    lpc = LeckPullChecker()
    lpc.check()