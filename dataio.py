"""YAML 로더 공용 모듈.

PyYAML은 YAML 1.1 규칙이라 `no`, `yes`, `on`, `off`를 불리언으로 읽는다.
스키마에 `no: 1`(작품 번호) 키가 있으므로, true/false만 불리언으로 인식하는 로더를 쓴다.
"""
import re
from pathlib import Path

import yaml


class Loader(yaml.SafeLoader):
    pass


# 기본 bool resolver 제거 후 true/false만 다시 등록
Loader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:bool"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$"), list("tf")
)


def load(path):
    return yaml.load(Path(path).read_text(encoding="utf-8"), Loader=Loader)
