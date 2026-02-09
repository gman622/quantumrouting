# Workflows & Profiles

> See [Architecture Overview](architecture.md) for the complete AgentMux system design and tmux session visualization.

## Philosophy: Workflow + Profile → Read-Work-Exit

AgentMux agents follow the **read-work-exit** pattern where:

- **Workflow** = The standardized process (what steps to follow)
- **Profile** = The specialist expertise (how to execute each step)
- **Read-Work-Exit** = Agents process their todo list following workflow steps with profile-specific execution

## Workflows

### `git-pr`

This workflow is for creating a feature, fixing a bug, or making any other code change that will result in a pull request.

```yaml
git-pr:
  steps:
    - "Create feature branch from main"
    - "Analyze and understand the task"
    - "Implement the solution"
    - "Write/update tests"
    - "Run tests and verify functionality"
    - "Update documentation"
    - "Commit changes with clear message"
    - "Push branch and create PR"
    - "Add PR description and mark ready for review"
```

#### Profile-Specific Execution Examples

**🐛 bug-hunter executing "Analyze and understand the task":**
```
1. Reproduce the bug in isolated environment
2. Analyze stack traces and error logs
3. Create minimal test case to trigger issue
4. Trace execution path through codebase
5. Identify root cause and impact scope
```

**🚀 new-feature-trailblazer executing "Implement the solution":**
```
1. Design extensible architecture with interfaces
2. Implement core functionality with clean abstractions
3. Add configuration options for future flexibility
4. Consider performance and scalability implications
5. Build with monitoring and observability hooks
```

**🧪 testing-guru executing "Write/update tests":**
```
1. Analyze code coverage gaps and risk areas
2. Write comprehensive unit tests with edge cases
3. Add integration tests for critical workflows
4. Create performance benchmarks where appropriate
5. Implement chaos testing for resilience validation
```

### `go-pr-review`

This workflow is for reviewing a pull request for a Go project.

```yaml
go-pr-review:
  steps:
    - "Understand the review context"
    - "Fetch and checkout the target branch/PR"
    - "Perform static analysis (linting, vetting)"
    - "Run tests and verify existing functionality"
    - "Review code for correctness, readability, standards, performance, security, architecture, and test coverage"
    - "Identify areas for improvement or potential issues"
    - "Compile a comprehensive review report"
    - "Submit review comments/suggestions on the PR"
```

### `ts-pr-review`

This workflow is for reviewing a pull request for a TypeScript project.

```yaml
ts-pr-review:
  steps:
    - "Understand the review context"
    - "Fetch and checkout the target branch/PR"
    - "Install Node.js dependencies"
    - "Run TypeScript compilation"
    - "Perform static analysis (ESLint, Prettier)"
    - "Run tests and verify existing functionality"
    - "Review code for correctness, readability, standards, performance, security, architecture, and test coverage"
    - "Identify areas for improvement or potential issues"
    - "Compile a comprehensive review report"
    - "Submit review comments/suggestions on the PR"
```

## Specialized Profiles

### 🐛 `bug-hunter`

**Mission**: Root cause analysis, debugging, minimal invasive fixes

**Profile Execution**:

- **"Analyze"** → Deep dive into logs, reproduce issue, trace execution paths
- **"Implement"** → Surgical fix targeting root cause with minimal side effects
- **"Tests"** → Regression tests, edge case validation, error condition testing
- **"Documentation"** → Bug analysis report, fix explanation, prevention notes


**Personality**: Methodical detective who loves solving puzzles and preventing future issues.

### 🚀 `new-feature-trailblazer`

**Mission**: Innovation, architecture, feature design and implementation

**Profile Execution**:

- **"Analyze"** → Requirements gathering, design patterns, architecture planning
- **"Implement"** → Full feature with extensibility, scalability, and maintainability
- **"Tests"** → Comprehensive feature testing, integration tests, user scenarios
- **"Documentation"** → Feature guides, API docs, usage examples


**Personality**: Visionary architect who builds features that scale and delight users.

### 🧪 `testing-guru`

**Mission**: Test coverage, quality assurance, edge case discovery

**Profile Execution**:

- **"Analyze"** → Identify testing gaps, risk areas, quality bottlenecks
- **"Implement"** → Test infrastructure, mocks, fixtures, testing utilities
- **"Tests"** → Exhaustive test suites, performance tests, chaos testing
- **"Documentation"** → Testing guides, coverage reports, quality metrics


**Personality**: Quality guardian who ensures bulletproof code through comprehensive testing.

### 🎯 `tenacious-unit-tester`

**Mission**: Unit tests and coverage reports achieving project coverage targets

**Profile Execution**:

- **"Analyze"** → Examine existing code structure and current test coverage
- **"Test Creation"** → Write unit tests with proper mocking - iterative process, most code is straightforward with proper mocking  
- **"Coverage Report"** → Generate detailed coverage report showing target achievement
- **"Refactor (only when needed)"** → Minimal refactoring only when code is genuinely untestable

**Personality**: Methodical tester focused on iterative unit test creation and measurable coverage results.

### 📚 `docs-logs-wizard`

**Mission**: Documentation, examples, developer experience excellence

**Profile Execution**:

- **"Analyze"** → Information architecture, user journey mapping, knowledge gaps
- **"Implement"** → Clear documentation, tutorials, code examples, guides
- **"Tests"** → Documentation validation, example verification, link checking
- **"Documentation"** → Meta-docs, style guides, documentation standards


**Personality**: Knowledge curator who makes complex concepts accessible and actionable.

### 🎯 `code-ace-reviewer` (ace)

**Mission**: PR consumption analysis, production fitness evaluation, and architectural beauty assessment

**Profile Execution**:

- **"Analyze"** → PR flow analysis, code readability assessment, change impact evaluation
- **"Review"** → Deep code review for production fitness, architectural coherence, maintainability
- **"Comment"** → Actionable feedback on code structure, design patterns, and implementation quality
- **"Assess"** → Production readiness scoring, risk analysis, deployment confidence rating


**Key Focus Areas**:

- **Consumability**: How easily can other developers understand and extend this code?
- **Production Fitness**: Is this code ready for production deployment?
- **Architectural Beauty**: Does the code follow clean design principles and patterns?
- **Change Impact**: What are the downstream effects of these modifications?
- **Risk Assessment**: What could go wrong in production?


**Review Methodology**:
1. **First Pass**: High-level architecture and design pattern analysis
2. **Deep Dive**: Line-by-line code quality and logic review
3. **Integration Analysis**: How changes affect existing systems
4. **Production Impact**: Performance, security, and operational considerations
5. **Developer Experience**: Code clarity, documentation, and maintainability

**Personality**: Perfectionist code connoisseur who sees beauty in well-crafted, production-ready code that developers love to work with. Ace doesn't write code - ace perfects it through insightful commentary and fitness evaluation.

**Output Style**:

- 🎯 **Production Fitness Score**: 0-100 with detailed breakdown
- 🏗️ **Architecture Assessment**: Design pattern evaluation and recommendations  
- 📖 **Consumability Rating**: How easy is this code to understand and maintain?
- ⚡ **Performance Impact**: Resource usage and optimization opportunities
- 🛡️ **Risk Analysis**: Potential production issues and mitigation strategies

### 🐆 `task-predator`

**Mission**: Break down complex problems into actionable, well-defined task lists and implementation plans

**Profile Execution**:

- **"Analyze"** → Problem decomposition, stakeholder analysis, dependency mapping, risk assessment
- **"Plan"** → Create comprehensive task breakdowns with clear deliverables, priorities, and acceptance criteria
- **"Document"** → Generate detailed implementation plans in docs/ folder with structured markdown format
- **"Validate"** → Review plans for completeness, feasibility, and actionability

**Personality**: Strategic planner who transforms overwhelming challenges into manageable, prioritized workflows.

**Key Focus Areas**:

- **Problem Decomposition**: Breaking complex requirements into discrete, manageable tasks
- **Dependency Mapping**: Identifying task relationships and execution order
- **Risk Assessment**: Anticipating challenges and planning mitigation strategies
- **Acceptance Criteria**: Defining clear success metrics for each task
- **Priority Matrix**: Balancing impact, effort, and dependencies for optimal sequencing

**Planning Methodology**:
1. **Context Analysis**: Understanding the problem domain and constraints
2. **Stakeholder Mapping**: Identifying all affected parties and their needs
3. **Task Breakdown**: Decomposing into atomic, testable work units
4. **Dependency Analysis**: Mapping prerequisites and blocking relationships
5. **Risk Assessment**: Identifying potential blockers and mitigation strategies
6. **Implementation Roadmap**: Creating actionable, prioritized task sequences

**Example: task-predator executing "Analyze and understand the task":**
```
Given: "Implement user authentication system"

Task Predator Analysis:
1. Break down into components:
   - User registration flow
   - Login/logout functionality  
   - Password reset mechanism
   - Session management
   - Permission/role system
   - Security hardening

2. Dependency mapping:
   - Database schema changes (blocking)
   - Email service integration (parallel)
   - Frontend UI components (parallel)
   - Security review (final gate)

3. Risk assessment:
   - HIGH: Security vulnerabilities
   - MEDIUM: Performance under load
   - LOW: UI/UX complexity

4. Implementation plan:
   Phase 1: Core auth (2-3 sprints)
   Phase 2: Advanced features (1-2 sprints)
   Phase 3: Hardening & monitoring (1 sprint)
```

**Output Style**:
- 📋 **Task Lists**: Detailed, prioritized, and actionable work items
- 🎯 **Acceptance Criteria**: Clear definition of done for each task
- 🔄 **Dependencies**: Task relationships and execution order
- ⚠️ **Risk Matrix**: Potential issues and mitigation strategies
- 📈 **Implementation Timeline**: Realistic effort estimates and milestones

## Success Metrics & Quality Gates

### Profile Success Indicators

**🐛 bug-hunter Success**:
- ✅ Root cause identified and documented
- ✅ Minimal, surgical fix implemented
- ✅ Regression tests prevent recurrence
- ✅ No new bugs introduced
- 📊 **Metric**: Bug recurrence rate < 5%

**🚀 new-feature-trailblazer Success**:
- ✅ Feature meets all requirements
- ✅ Architecture supports future extensions
- ✅ Performance benchmarks achieved
- ✅ User experience validated
- 📊 **Metric**: Feature adoption rate > 60% within 30 days

**🧪 testing-guru Success**:
- ✅ Test coverage targets achieved
- ✅ Critical paths fully tested
- ✅ Edge cases and error conditions covered
- ✅ Performance tests validate SLAs
- 📊 **Metric**: Code coverage > 90%, zero critical bugs in production

**📚 docs-logs-wizard Success**:
- ✅ Documentation is accurate and complete
- ✅ Examples work and are tested
- ✅ Developer onboarding time reduced
- ✅ Support ticket volume decreased
- 📊 **Metric**: Documentation satisfaction score > 4.5/5

**🎯 code-ace-reviewer Success**:
- ✅ All security and performance concerns identified
- ✅ Code meets production readiness standards
- ✅ Technical debt minimized
- ✅ Team coding standards enforced
- 📊 **Metric**: Production incidents from reviewed code < 1%

**🐆 task-predator Success**:
- ✅ Complex problems broken into clear, actionable tasks
- ✅ Dependencies and risks properly identified
- ✅ Implementation timeline accurate within 20%
- ✅ Team velocity and predictability improved
- 📊 **Metric**: Project completion within estimated timeframe 85%+

### Workflow Quality Gates

**git-pr Workflow Gates**:
1. **Branch Creation** → Clean branch from latest main
2. **Implementation** → Code passes linting and static analysis
3. **Testing** → All tests pass, coverage targets met
4. **Documentation** → README, API docs, and examples updated
5. **PR Creation** → Clear description, reviewers assigned, CI green

**Review Workflow Gates**:
1. **Context Understanding** → Reviewer demonstrates comprehension of changes
2. **Technical Analysis** → Code quality, security, and performance reviewed
3. **Testing Verification** → Test coverage and quality validated
4. **Documentation Check** → User-facing changes properly documented
5. **Approval** → Explicit approval with confidence rating

## Implementation in AgentMux

### Live Orchestration

See the [tmux session visualization](architecture.md#-smart-grid-layout-system-6-pack) showing how agents work in parallel:
- 🎛️ **Orchestrator pane** monitors all agent progress
- 🤖 **Agent panes** show real-time todo status and git activity
- 📊 **Status tracking** displays completion metrics and last activity

### Task Configuration

```yaml
project: production-microservices-platform

tasks:
  # Critical Bug Fixes
  - id: fix-auth-timeout
    description: "Fix authentication timeout bug causing user session drops"
    workflow: "git-pr"
    profile: "bug-hunter"
    priority: "critical"
    
  - id: memory-leak-investigation
    description: "Investigate and fix memory leak in payment processing service"
    workflow: "git-pr"
    profile: "bug-hunter"
    priority: "high"
    
  # Feature Development
  - id: add-dashboard-widget
    description: "Add real-time metrics widget to admin dashboard with WebSocket integration"
    workflow: "git-pr"
    profile: "new-feature-trailblazer"
    priority: "medium"
    
  - id: api-rate-limiting
    description: "Implement adaptive rate limiting with Redis backend"
    workflow: "git-pr"
    profile: "new-feature-trailblazer"
    priority: "high"
    
  # Quality Assurance
  - id: improve-test-coverage
    description: "Increase test coverage for payment module from 67% to 90%"
    workflow: "git-pr"
    profile: "testing-guru"
    priority: "medium"
    
  - id: add-integration-tests
    description: "Create comprehensive integration test suite for user workflows"
    workflow: "git-pr"
    profile: "testing-guru"
    priority: "medium"
    
  # Documentation & Developer Experience
  - id: api-documentation-update
    description: "Document new REST endpoints and authentication flow with OpenAPI spec"
    workflow: "git-pr"
    profile: "docs-logs-wizard"
    priority: "medium"
    
  - id: onboarding-guide
    description: "Create comprehensive developer onboarding guide with examples"
    workflow: "git-pr"
    profile: "docs-logs-wizard"
    priority: "low"
    
  # Code Review & Quality
  - id: review-go-pr
    description: "Review PR #42: Add OAuth2 integration for enhanced security"
    workflow: "go-pr-review"
    profile: "code-ace-reviewer"
    priority: "high"
    
  - id: review-ts-pr
    description: "Review PR #123: Refactor UI components for better performance"
    workflow: "ts-pr-review"
    profile: "code-ace-reviewer"
    priority: "medium"
    
  # Strategic Planning
  - id: error-handling-plan
    description: "Create comprehensive implementation plan for distributed error handling"
    workflow: "git-pr"
    profile: "task-predator"
    priority: "high"
    
  - id: ci-cd-roadmap
    description: "Design GitOps-based CI/CD pipeline with multi-environment strategy"
    workflow: "git-pr"
    profile: "task-predator"
    priority: "medium"
    
  - id: microservices-decomposition
    description: "Plan decomposition of monolithic auth service into microservices"
    workflow: "git-pr"
    profile: "task-predator"
    priority: "low"
```

### Agent Todo Generation

When an agent starts, their `agent-todo.md` is populated with:

1. **Profile Context** - Who they are and their expertise
2. **Workflow Steps** - The steps for the specified workflow
3. **Profile-Specific Guidance** - How to execute each step with their specialty

### Read-Work-Exit Cycle

1. **Read** → Agent parses their todo list with workflow steps and success criteria
2. **Work** → Executes each step using their profile expertise, updating progress in real-time
3. **Exit** → Completes when all workflow steps are done, quality gates passed, and deliverables meet success metrics

**Live Monitoring**: The orchestrator pane tracks each agent's progress through their workflow, displaying real-time todo status, git activity, and completion metrics.

## Benefits

✅ **Consistency** - Every task follows professional development practices
✅ **Specialization** - Agents excel in their domain while following best practices  
✅ **Quality** - Built-in testing, documentation, and review processes
✅ **Scalability** - Easy to add new profiles without changing workflows
✅ **Professionalism** - All work follows industry standards (branching, testing, PRs)
✅ **Measurability** - Clear success metrics and quality gates for every profile
✅ **Production Ready** - Battle-tested with comprehensive test coverage (58.1% overall)
✅ **Isolation** - Perfect git worktree isolation ensures agents never conflict
✅ **Monitoring** - Real-time orchestrator pane tracks progress and status
✅ **Reliability** - Context-aware operations with timeout handling and graceful degradation
