\# CookVault AI Integration



\## Objective



Add a local AI assistant to the existing CookVault web application.



The AI should use the existing local Qwen model as its reasoning engine and integrate directly with CookVault through a controlled backend tool layer.



Do \*\*not\*\* fine-tune or retrain Qwen as part of this implementation.



Instead, build an agent architecture using:



\* System prompting

\* Tool/function calling

\* Structured outputs

\* Existing CookVault database/services

\* Recipe drafts and user approval

\* Optional RAG where it provides real value

\* Conversation context



The AI should behave like a native CookVault feature, not a separate chatbot bolted onto the application.



\---



\# 1. Inspect the Existing Application First



Before writing code, inspect the entire CookVault project and understand the current architecture.



Identify:



\* Frontend framework

\* Backend/API architecture

\* Database schema

\* ORM/database access patterns

\* Authentication

\* Recipe models

\* Ingredient models

\* Recipe draft models

\* Meal planning models

\* Shopping list models

\* Existing service layers

\* Existing validation schemas

\* Existing API conventions

\* Existing UI/component conventions

\* Existing import/review workflow

\* Existing provenance handling



Reuse existing systems wherever possible.



Do not create duplicate models, services, schemas, or APIs when CookVault already has an appropriate abstraction.



Prefer small, additive, reversible changes over large rewrites.



Before implementation, produce a short architecture plan explaining what you found and exactly what you intend to change.



Wait for approval before making substantial architectural changes.



\---



\# 2. Core Architecture



Implement the AI approximately as:



```text

CookVault UI

&#x20;    │

&#x20;    ▼

CookVault AI API

&#x20;    │

&#x20;    ▼

AI Orchestrator

&#x20;    │

&#x20;    ├──── Qwen / Local Model

&#x20;    │

&#x20;    ├──── CookVault Tools

&#x20;    │

&#x20;    ├──── Conversation Context

&#x20;    │

&#x20;    └──── Optional RAG

&#x20;               │

&#x20;               ▼

&#x20;         CookVault Services

&#x20;               │

&#x20;               ▼

&#x20;         CookVault Database

```



The model must NEVER receive direct database credentials or unrestricted database access.



Qwen may request operations through explicitly defined CookVault tools.



The server remains responsible for:



\* Authentication

\* Authorization

\* Input validation

\* Database operations

\* Business rules

\* Audit logging

\* User confirmation

\* Error handling



The AI proposes actions.



CookVault decides whether those actions are valid and executes them.



\---



\# 3. Model Provider Abstraction



Do not tightly couple CookVault to Qwen or Ollama.



Create a model/provider abstraction such as:



```text

AIProvider

&#x20;   │

&#x20;   ├── LocalQwenProvider

&#x20;   │

&#x20;   ├── OllamaProvider

&#x20;   │

&#x20;   └── FutureProvider

```



The rest of CookVault should communicate with the provider interface rather than model-specific APIs.



The initial provider should connect to the local Qwen deployment already available in the environment.



Configuration should come from environment/configuration values rather than hardcoded addresses.



Example conceptual configuration:



```env

AI\_PROVIDER=ollama

AI\_MODEL=qwen

AI\_BASE\_URL=http://localhost:11434

```



Do not assume these exact values are correct.



Inspect the environment and existing configuration first.



\---



\# 4. AI Chat



Add an AI chat experience to CookVault.



The assistant should be able to handle natural conversations such as:



```text

What can I cook with chicken tonight?

```



```text

Show me recipes that take less than 30 minutes.

```



```text

What am I cooking Thursday?

```



```text

Add my mom's chili recipe.

```



```text

Double the chili recipe.

```



```text

What can I substitute for buttermilk?

```



```text

Add the ingredients for lasagna to my shopping list.

```



Prefer streaming responses when supported by the existing stack and local model API.



Conversation failures should degrade gracefully rather than breaking the UI.



\---



\# 5. CookVault AI Tools



Create a controlled tool registry.



Tools should use existing CookVault services rather than implementing database logic inside the AI layer.



Initial read-only tools should include equivalents of:



```text

search\_recipes

get\_recipe

get\_recipe\_ingredients

get\_meal\_plan

search\_ingredients

get\_shopping\_list

```



Once read-only operations are reliable, add controlled write operations such as:



```text

create\_recipe\_draft

update\_recipe\_draft

add\_recipe\_to\_meal\_plan

add\_to\_shopping\_list

generate\_shopping\_list

```



Use the names appropriate for the existing codebase.



Do not duplicate existing service methods merely to match these names.



\---



\# 6. Recipe Creation



One of the primary AI features is conversational recipe creation.



Example:



```text

User:

Add my mom's chili.



It uses two pounds of ground beef, two cans of kidney

beans, tomato sauce, an onion, chili powder and garlic.



Brown the beef first, then add everything else and

simmer for about an hour.

```



The AI should extract structured recipe information.



Example conceptual result:



```json

{

&#x20; "title": "Mom's Chili",

&#x20; "ingredients": \[

&#x20;   {

&#x20;     "quantity": 2,

&#x20;     "unit": "lb",

&#x20;     "name": "ground beef"

&#x20;   },

&#x20;   {

&#x20;     "quantity": 2,

&#x20;     "unit": "can",

&#x20;     "name": "kidney beans"

&#x20;   },

&#x20;   {

&#x20;     "name": "tomato sauce"

&#x20;   },

&#x20;   {

&#x20;     "quantity": 1,

&#x20;     "name": "onion"

&#x20;   },

&#x20;   {

&#x20;     "name": "chili powder"

&#x20;   },

&#x20;   {

&#x20;     "name": "garlic"

&#x20;   }

&#x20; ],

&#x20; "instructions": \[

&#x20;   "Brown the ground beef.",

&#x20;   "Add the remaining ingredients.",

&#x20;   "Simmer for approximately 1 hour."

&#x20; ]

}

```



This output MUST be validated using the application's schema validation system.



If CookVault uses Zod, reuse Zod.



Do not trust model-generated JSON without validation.



\---



\# 7. Draft-First Recipe Workflow



AI-generated recipes must NOT automatically become permanent recipes.



The flow should be:



```text

User request

&#x20;     ↓

AI extracts recipe

&#x20;     ↓

Server validates structure

&#x20;     ↓

Recipe Draft

&#x20;     ↓

Review/Edit UI

&#x20;     ↓

User approves

&#x20;     ↓

Permanent Recipe

```



This should integrate with CookVault's existing recipe draft/import review architecture.



AI recipe creation is another input source for the same draft pipeline.



Do not create a separate AI-only recipe system unless absolutely necessary.



\---



\# 8. Provenance



Preserve recipe provenance.



AI-created or AI-parsed drafts should record information necessary to understand their origin.



For example:



```text

source\_type = ai\_chat

source\_model = <model>

original\_text = <user supplied recipe text>

created\_by = <user>

```



Adapt this to the existing provenance model.



The user's original recipe text should not be discarded if CookVault already supports retaining source material.



\---



\# 9. Missing Information



The AI must distinguish between:



\* information explicitly provided by the user

\* reasonable formatting/normalization

\* information it would have to invent



Do not invent important recipe facts.



For example, if the user says:



```text

Add chicken tacos.

```



The AI should not silently invent an entire chicken taco recipe.



It should ask for additional information.



Likewise:



```text

User:

Add my chili recipe.



AI:

Sure. What ingredients and instructions should I use?

```



Minor normalization is acceptable.



Fabrication is not.



\---



\# 10. Read Operations



The assistant should be able to answer questions using actual CookVault data.



Example:



```text

User:

What recipes do I have with chicken?

```



The model should call:



```text

search\_recipes

```



The server returns real CookVault results.



The AI then summarizes those results.



The AI must NEVER claim that a recipe, ingredient, meal plan, or shopping-list item exists unless that information came from CookVault or was explicitly supplied during the conversation.



\---



\# 11. Write Operations



Treat AI writes differently from reads.



Classify tools approximately as:



```text

READ

WRITE\_DRAFT

WRITE

DESTRUCTIVE

```



READ operations may execute automatically when authorized.



WRITE\_DRAFT operations may create temporary/reviewable data.



WRITE operations should follow existing application confirmation/business rules.



DESTRUCTIVE operations require explicit user confirmation.



Examples of destructive operations include:



\* deleting recipes

\* replacing recipes

\* clearing shopping lists

\* removing meal plans

\* bulk modification



The model itself cannot bypass these requirements.



Enforcement must occur server-side.



\---



\# 12. Structured Tool Calling



Use native model tool/function calling where supported.



Each tool must have:



\* Name

\* Description

\* Input schema

\* Validation

\* Authorization requirements

\* Handler

\* Structured result

\* Error handling



Conceptually:



```ts

interface AITool<TInput, TResult> {

&#x20; name: string;

&#x20; description: string;

&#x20; schema: unknown;



&#x20; execute(

&#x20;   input: TInput,

&#x20;   context: AIToolContext

&#x20; ): Promise<TResult>;

}

```



Adapt this interface to the existing architecture.



Do not blindly introduce abstractions if CookVault already has an equivalent pattern.



\---



\# 13. Agent Loop



Implement a bounded agent/tool loop.



Conceptually:



```text

User message

&#x20;    ↓

Qwen

&#x20;    ↓

Tool request?

&#x20;┌───────┴────────┐

No               Yes

│                 │

▼                 ▼

Answer       Validate Tool

&#x20;                 │

&#x20;                 ▼

&#x20;            Execute Tool

&#x20;                 │

&#x20;                 ▼

&#x20;            Tool Result

&#x20;                 │

&#x20;                 ▼

&#x20;               Qwen

&#x20;                 │

&#x20;                 ▼

&#x20;              Answer

```



Prevent infinite tool loops.



Use a configurable maximum number of tool iterations.



Log tool failures.



A tool failure should be returned to the model in a controlled format so it can explain the failure rather than hallucinating success.



\---



\# 14. System Prompt



Create a dedicated CookVault system prompt.



Store it somewhere maintainable rather than embedding a giant string inside application code.



The prompt should establish rules similar to:



```text

You are CookVault's cooking assistant.



Your purpose is to help the user manage recipes, plan meals,

understand cooking techniques, and use CookVault.



CookVault's database is the source of truth for the user's

recipes, meal plans, ingredients, and shopping lists.



Never claim CookVault contains information unless it was

returned by a CookVault tool.



Use tools when information from CookVault is required.



Never pretend a tool succeeded when it returned an error.



When creating recipes from conversation, create a recipe

draft rather than directly saving a permanent recipe.



Preserve information supplied by the user.



Do not invent important missing quantities, temperatures,

times, ingredients, or instructions.



Ask concise follow-up questions when important information

is missing.



Prefer concise and practical cooking answers.



For potentially destructive operations, require explicit

confirmation before proceeding.

```



Expand this as necessary while keeping it maintainable.



\---



\# 15. RAG



Do not build a massive RAG system simply because AI is involved.



First determine whether CookVault actually needs one.



CookVault database information should generally come from tools, not RAG.



RAG is appropriate for relatively static reference information such as:



\* Cooking techniques

\* Ingredient substitution guides

\* Measurement references

\* Food terminology

\* User cooking notes

\* Imported cooking documentation



Keep RAG separate from operational application data.



Conceptually:



```text

CookVault DB → Tools



Cooking Knowledge → RAG

```



Do not embed the entire transactional database into a vector store.



\---



\# 16. Conversation Context



Support conversation continuity.



The assistant should understand exchanges such as:



```text

User:

Find my chili recipe.



Assistant:

I found Mom's Chili.



User:

Double it.

```



The second request should understand that "it" refers to the recipe retrieved immediately before it.



Avoid sending unlimited chat history to the model.



Implement a sensible context strategy.



If persistent AI conversations are stored, ensure they are associated with the authenticated user.



\---



\# 17. Chat UI



Add a native CookVault AI chat interface.



The exact design should match the existing CookVault UI.



Possible entry points include:



```text

Ask CookVault

```



or:



```text

CookVault Assistant

```



The interface should support:



\* User messages

\* Assistant messages

\* Streaming responses

\* Loading state

\* Tool activity state

\* Error state

\* Recipe draft preview

\* Links/actions to open recipes

\* Links/actions to review generated drafts

\* Clear conversation

\* New conversation



Do not expose raw model/tool JSON to normal users.



Tool activity may be represented simply:



```text

Searching your recipes...

```



or:



```text

Creating recipe draft...

```



\---



\# 18. Security



Treat model output as untrusted input.



All model-generated tool arguments must be validated.



Never allow the model to:



\* Execute arbitrary SQL

\* Execute arbitrary shell commands

\* Access unrestricted filesystem paths

\* Supply arbitrary backend URLs

\* Bypass authentication

\* Bypass authorization

\* Call unspecified internal APIs

\* Read secrets

\* Read environment variables

\* Dynamically construct executable code



Tools should be explicitly registered.



Unknown tool requests must be rejected.



Protect against prompt injection contained inside recipes or imported content.



Recipe text is DATA, not trusted instructions to the AI system.



\---



\# 19. Audit Logging



AI write operations should be auditable.



Capture enough information to reconstruct important operations.



Example:



```text

conversation\_id

user\_id

model

tool\_name

validated\_arguments

result

timestamp

confirmation\_required

confirmation\_received

affected\_record\_id

```



Do not log secrets or unnecessary sensitive information.



The important lifecycle should be visible:



```text

AI proposed

&#x20;    ↓

validated

&#x20;    ↓

user approved

&#x20;    ↓

saved

```



\---



\# 20. Observability



Add useful AI diagnostics without flooding normal application logs.



Track things such as:



```text

provider

model

request duration

tool calls

tool duration

tool failures

validation failures

model errors

context size

```



If token usage is available from the provider, capture it.



Logging should make it possible to determine whether a failure came from:



```text

UI

API

AI orchestrator

model

tool

database

```



\---



\# 21. Graceful Failure



CookVault must remain fully usable if the local AI is offline.



If Qwen cannot be reached:



```text

CookVault Assistant is currently unavailable.

```



Normal recipe management, meal planning, and shopping-list functionality must continue working.



The AI is an enhancement to CookVault, not a runtime dependency for the application.



\---



\# 22. Testing



Add tests for the AI integration.



At minimum test:



\### Tool Validation



Invalid model arguments must be rejected.



\### Authorization



AI tools cannot access another user's data.



\### Recipe Extraction



Known recipe text produces the expected structured draft.



\### Missing Information



The AI does not fabricate critical recipe information.



\### Draft Safety



AI-generated recipes cannot bypass the review/draft workflow.



\### Tool Failure



The assistant does not claim success when a tool fails.



\### Destructive Actions



Destructive operations cannot occur without confirmation.



\### Provider Failure



CookVault continues functioning when the AI provider is unavailable.



\---



\# 23. Initial MVP



Do not attempt every possible AI feature immediately.



The first usable version should focus on:



```text

AI Chat

&#x20;  │

&#x20;  ├── General cooking questions

&#x20;  │

&#x20;  ├── Search CookVault recipes

&#x20;  │

&#x20;  ├── View recipe information

&#x20;  │

&#x20;  ├── Query meal plans

&#x20;  │

&#x20;  └── Create recipe drafts from conversation

```



After these work reliably, expand into:



```text

Meal planning

Shopping lists

Recipe scaling

Recipe modification

Ingredient substitutions

Pantry-aware suggestions

RAG

More advanced agent workflows

```



Reliability matters more than the number of tools.



\---



\# 24. Important Architectural Principle



Do NOT "train Qwen on CookVault."



The intended architecture is:



```text

Qwen

&#x20; │

&#x20; ├── System Prompt → behavior

&#x20; │

&#x20; ├── Tools → live CookVault data/actions

&#x20; │

&#x20; ├── Conversation → current context

&#x20; │

&#x20; └── RAG → reference knowledge

```



CookVault remains the source of truth.



The model should be replaceable.



The AI integration should survive replacing Qwen with another local or remote model later.



\---



\# 25. Implementation Process



Work incrementally.



Before coding:



1\. Inspect the repository.

2\. Map the existing relevant architecture.

3\. Identify reusable services and schemas.

4\. Identify where AI integration belongs.

5\. Identify security boundaries.

6\. Propose the implementation plan.

7\. List files that will be created or modified.

8\. Identify any database migrations required.

9\. Identify assumptions or unresolved questions.



Then STOP.



Present the architecture and implementation plan for approval before making substantial changes.



Do not perform a large rewrite.



Do not replace working CookVault functionality unnecessarily.



Prefer additive changes.



After approval, implement one phase at a time and verify each phase before continuing.



The finished result should feel like CookVault gained an intelligent interface to its existing capabilities—not like a second application was built inside it.



