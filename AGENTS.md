# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## [Anti-Overengineering Directive]
- **YAGNI (You Aren't Gonna Need It)**: 현재 명시적으로 요구된 기능만 구현하십시오. 미래의 확장성이나 가상의 요구사항을 가정한 추상화, 인터페이스, 설정 분리를 미리 만들지 마십시오.
- **Keep It Flat & Direct**: 불필요한 계층 분할, 과도한 디자인 패턴, 중첩 래핑을 피하십시오. 가장 직관적이고 호출 깊이(Indirection)가 얕은 구현 방식을 우선합니다.
- **Minimal Surface Area**: 문제를 해결하는 데 필요한 최소한의 파일과 코드만 작성하십시오. 코드가 여러 레이어로 흩어지지 않고 데이터 흐름을 한눈에 파악할 수 있어야 합니다.
- **Proportional Complexity**: 해결하려는 문제보다 솔루션의 구조가 더 복잡해서는 안 됩니다. 요구사항을 완벽히 만족하는 가장 단순한 코드가 최선의 코드입니다.