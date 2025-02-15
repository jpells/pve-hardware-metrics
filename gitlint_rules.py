"""Define custom gitlint rules for commit message validation."""

import re

from gitlint.rules import CommitMessageTitle, LineRule, RuleViolation


class GitmojiConventionalCommit(LineRule):
    """Enforces Gitmoji + Conventional Commits format."""

    name = "gitmoji-conventional-commits"
    id = "GCC1"
    target = CommitMessageTitle

    GITMOJI_PATTERN = r"^(:\w+:\s)"
    CONVENTIONAL_PATTERN = (
        r"(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
        r"(\([a-z-]+\))?!?:\s.+"
    )
    RULE_REGEX = re.compile(f"{GITMOJI_PATTERN}?{CONVENTIONAL_PATTERN}")

    def validate(self, line: str, _commit: CommitMessageTitle) -> list[RuleViolation]:
        """Validate commit message against Gitmoji + Conventional Commits format."""
        violations = []
        match = self.RULE_REGEX.match(line)

        if not match:
            msg = (
                "Title does not follow Gitmoji + ConventionalCommits format "
                "':gitmoji: type(optional-scope): description'"
            )
            violations.append(RuleViolation(self.id, msg, line))

        return violations
