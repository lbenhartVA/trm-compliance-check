# Code Project Template

This repository is a template for development of a tool to verify adherence to the VA TRM

## Code Description

Given a yaml file with a list of trm entries, search the public trm and verify compliance.

The structure of the dictionary:

``` yaml
trm_entries:
  - name: Red Hat Enterprise Linux (RHEL)
    tid: 6367
    decision: "Authorized w/ Constraints [18, 20, 22, 23]"
    version: "8.x"
    approval_date: "02/05/2025"
```

Compliance rules:
 - for each tid, the version level is a match for the current quaarter on the decision tab

Compliance Conditions:
for current CY Quarter of report execution
  - InCompliance: version matches, decision matches
  - InDivest: version matches, the decision is changed to Divest
  - Unapproved: version or decision does not match

Output:
 - json file of each tid, its compliance status, the date from the trm of the decision
 - html file with neatly formatted table of results

### Deployment


#### Branching strategy

**UPDATE THIS FOR YOUR PROJECT AND BUILD STRATEGY**

Certain branches are special, and would ordinarily be deployed to various test environments:

- master: our default branch, for production-ready code. Master is always deployable. In our case, however, deployment does not happen automatically.

New code should be produced on a feature branch [following GitHub flow](https://guides.github.com/introduction/flow/). 
Most often, you'll want to branch from **master**, since that's the latest in production. 
File a pull request to merge into **test**, which can be deployed to our testing environment.



### Testing




### Installing




### License

See the [LICENSE](LICENSE.md) file for license rights and limitations.
