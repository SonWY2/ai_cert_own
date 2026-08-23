# Python 플러그인 기반 모듈형 아키텍처 가이드 (Plugin Architecture Guide)

본 문서는 시스템 확장성과 유지보수성을 극대화하기 위한 **플러그인 기반 모듈형 Python 시스템 아키텍처** 표준 가이드입니다. 특정 도메인에 종속되지 않는 범용적인 설계 패턴(Composite Pattern + Self-Dispatching)을 기반으로 구성됩니다.

---

## 1. 핵심 설계 원칙

* **모듈 단위 격리 (Module-Level Isolation):** 도메인 및 기능 단위로 디렉토리를 분리하여 모듈 간 의존성을 최소화합니다.
* **코어 오케스트레이션 유지 (Core-at-Root):** 모듈의 메인 제어 흐름은 모듈 최상위 경로(`orchestrator.py`)에 상주하며, 전체 실행 순서 제어와 플러그인 호출만 담당합니다.
* **인터페이스 단일화 (Composite Pattern):** 일반 단일 플러그인과 하위 플러그인을 포함하는 재귀형 플러그인이 동일한 인터페이스(`execute`, `can_handle`)를 공유합니다. 상위 로직은 하위 플러그인의 중첩 여부를 구분하지 않고 동일한 방식으로 호출합니다.
* **스크립트 500줄 제한 (Max 500 LOC):** 모든 `.py` 파일은 **최대 500줄**을 초과할 수 없습니다. 500줄에 도달하면 하위 플러그인 또는 헬퍼 스크립트로 분할합니다.
* **문서 동기화 의무:** 각 모듈은 `CONTEXT.md`와 `USAGE.md`를 필수로 유지하며, 플러그인이나 기능 변경 시 코드와 함께 반드시 갱신합니다.

---

## 2. 디렉토리 구조 및 승격(Promotion) 규칙

### 2.1 표준 디렉토리 구조

```text
src/
└── modules/
    └── {module_name}/            # 개별 기능 모듈
        ├── __init__.py
        ├── CONTEXT.md            # 모듈 맥락, 아키텍처, 플러그인 구성 명세
        ├── USAGE.md              # 모듈 실행 방법, I/O 규격, 플러그인 확장 가이드
        ├── orchestrator.py       # 메인 제어 로직 (최상위 흐름 관리, ≤ 500 lines)
        │
        └── plugins/              # 기능 플러그인 디렉토리
            ├── __init__.py
            ├── base.py           # 기본 인터페이스 정의 (BasePlugin, CompositePlugin)
            ├── simple_plugin.py  # 단일 파일 플러그인 (단순 기능)
            │
            └── composite_plugin/ # 승격된 재귀 플러그인 (하위 커스텀 로직 필요 시)
                ├── __init__.py   # CompositePlugin을 상속한 부모 플러그인
                ├── sub_plugin_a.py # 하위 플러그인 A
                └── sub_plugin_b.py # 하위 플러그인 B

```

### 2.2 단일 파일 ↔ 폴더 승격(Promotion) 규칙

1. **기본 상태:** 플러그인은 `plugins/feature_plugin.py` 형태의 **단일 스크립트**로 시작합니다.
2. **승격 조건:** 코드 길이가 400~500줄에 도달하거나, 내부에 별도의 하위 분기 로직이 필요해지면 `plugins/feature_plugin/` **폴더로 승격**합니다.
3. **폴더 내부 구성:** 폴더 내 `__init__.py`가 부모 플러그인(`CompositePlugin`)이 되며, 세부 로직은 동일 폴더 내 하위 플러그인 스크립트(`sub_*.py`)로 분리합니다.

---

## 3. 플러그인 & 재귀 플러그인 설계 표준

### 3.1 자율 판단 디스패치 (`can_handle`)

오케스트레이터나 부모 플러그인에서 `if-elif` 문으로 데이터 종류나 타입을 직접 분기하지 않습니다. 각 플러그인이 `can_handle(target)`을 통해 처리 대상 여부를 스스로 판단합니다.

### 3.2 데이터 흐름 (Accumulator & Shallow Context)

* **Input:** 처리 대상 데이터 객체(`target: dict`) + 읽기 전용 공유 컨텍스트(`context: dict`)
* **Output:** 처리가 완료된 결과 딕셔너리(`dict`)
* 복잡한 공유 상태 객체 대신 단순 딕셔너리 누적(Accumulator) 방식을 사용하여 데이터 흐름을 단순하게 유지합니다.

### 3.3 표준 인터페이스 및 구현 템플릿

```python
# plugins/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BasePlugin(ABC):
    """모든 플러그인의 기본 인터페이스"""
    
    def can_handle(self, target: Dict[str, Any]) -> bool:
        """자신이 처리할 대상인지 판단 (기본값: True)"""
        return True

    @abstractmethod
    def execute(self, target: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """비즈니스 로직 실행 및 결과 반환"""
        pass


class CompositePlugin(BasePlugin):
    """하위 플러그인을 포함하는 재귀형 부모 플러그인"""
    
    def __init__(self, sub_plugins: List[BasePlugin] = None):
        self.sub_plugins = sub_plugins or []

    def execute(self, target: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        result = target
        for plugin in self.sub_plugins:
            if plugin.can_handle(result):
                result = plugin.execute(result, context)
        return result

```

```python
# plugins/composite_plugin/__init__.py (승격된 재귀 플러그인 예시)
from ..base import CompositePlugin
from .sub_plugin_a import SubPluginA
from .sub_plugin_b import SubPluginB

class CustomCompositePlugin(CompositePlugin):
    def __init__(self):
        super().__init__(sub_plugins=[
            SubPluginA(),
            SubPluginB()
        ])

    def can_handle(self, target: dict) -> bool:
        return target.get("type") == "TARGET_TYPE_A"

```

---

## 4. 모듈 필수 문서화 표준

모든 모듈은 코드와 동일한 커밋 단위로 아래 2개 문서를 작성하고 관리합니다.

### 4.1 `CONTEXT.md` (모듈 아키텍처 및 맥락 명세)

```markdown
# Module Context: {Module Name}

## 1. 개요
- 모듈의 핵심 책임 및 해결하려는 문제 정의

## 2. 오케스트레이션 파이프라인
- `orchestrator.py`의 전체 실행 흐름 및 플러그인 데이터 파이프라인 명세

## 3. 플러그인 목록
| 플러그인 명 | 형태 (단일/폴더) | 역할 | 처리 조건 (`can_handle`) |
| :--- | :--- | :--- | :--- |
| `simple_plugin` | 단일 파일 | 기본 단위 기능 처리 | `type == 'TARGET_TYPE_A'` |
| `composite_plugin` | 폴더 (재귀) | 복합 기능 및 하위 분기 처리 | `type == 'TARGET_TYPE_B'` |

## 4. 제약사항 및 의존성
- 처리 시 주의사항, 성능 고려사항 및 외부 의존성

```

### 4.2 `USAGE.md` (실행 명세 및 확장 가이드)

```markdown
# Module Usage: {Module Name}

## 1. 실행 방법 (Quick Start)
- 코드 내 호출 예시 및 CLI 실행 명령어

## 2. 입출력 규격 (I/O Specification)
- **Input:** 타겟 데이터 및 컨텍스트 포맷 명세
- **Output:** 최종 반환 딕셔너리 구조 명세

## 3. 신규 플러그인 추가 방법
1. `plugins/` 내에 `BasePlugin`을 상속하는 신규 스크립트 작성
2. 로직 확장이 필요할 경우 폴더로 승격 후 `CompositePlugin` 적용
3. `CONTEXT.md`의 플러그인 목록 갱신

```

---

## 5. 품질 관리 규격 요약

| 항목 | 기준 | 가이드라인 |
| --- | --- | --- |
| **코드 라인 수** | 파일당 최대 500줄 | 400줄 초과 시 단일 파일 플러그인을 폴더(`Composite`)로 승격 분할 |
| **디스패치 방식** | `can_handle()` 위임 | 오케스트레이터 및 상위 플러그인 내 하드코딩된 `if-elif` 분기 금지 |
| **중첩 깊이** | 최대 2단계 | `Module` -> `Plugin` -> `Sub-Plugin` 이상의 과도한 중첩 지양 |
| **문서 동기화** | 기능 변경 시 즉시 갱신 | 플러그인 추가/수정 시 `CONTEXT.md`, `USAGE.md` 동시 커밋 필수 |

```

