---
Name: orchestrator
Description: this orchestrator plugins give acces to a number of agents aimed to work together.
---

# Target

this is little brainstorming file on what i would like to implement

|orchestrator|sub-agents|goal|
|:-:|:-:|:-:|
| code | coding agents | one big model should delegate tasks to smaller models to produce code. by doing this the sub agent don't have full context, should save some tokens to produce an individual and simple part of the project (input: task, output: code, tests, attentions points), each agents is bound to a scope and don't have to edit outside of it |
| reflections | possibilites | for a descision to make start one agents for each possibilities and make them defend their idea at all cost, once all subagents answer make a descision based on the section `descisions` inside `CLAUDE.md`|

### questions

|subject|goal|
|:-:|:-:|
|practices|how to implement best prictices for each agents, let the user a customisation block|
|call sub-agent|define a format nice and clean|