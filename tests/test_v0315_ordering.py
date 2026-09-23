"""Commit order for the v0.3.15 round. This proves ancestry, not wall clocks.

A depth-1 checkout cannot see these commits. Unit CI fetches full history.
"""
import subprocess


ORDER = (
    "4681d444dc45905c8c644528dae7c253dd936233",  # protocol
    "5bf7e10b84ba6f37f70be90017ae1278e1013246",  # suite freeze
    "2a71ef53dc817012e139cb7588599d52f47f9d84",  # measurement
    "f81e62c28cb76195612c850fc3da60ad006e9f40",  # publication
)


def _ancestor(older: str, newer: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise AssertionError(
            "ordering check needs those commits in the checkout "
            f"(returncode {result.returncode}): {result.stderr.strip()}")
    return result.returncode == 0


def test_protocol_freeze_and_publication_are_ordered():
    for older, newer in zip(ORDER, ORDER[1:]):
        assert _ancestor(older, newer), (older, newer)
