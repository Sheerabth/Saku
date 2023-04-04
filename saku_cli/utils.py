import re


def find_matching_lines(regex: str, content: str) -> list[tuple[int, int, set[int]]]:
    re_pattern = re.compile(f"({regex})", re.MULTILINE | re.DOTALL)
    re_newline = re.compile(r"\n")
    line_nums = []

    for m in re_pattern.finditer(content):
        start_line = len(re_newline.findall(content, 0, m.start(0))) + 1
        end_line = len(re_newline.findall(content, 0, m.end(0))) + 1
        if line_nums:
            prev_start, prev_end, matched_lines = line_nums[-1]
            if abs(start_line - prev_end) < 5:
                matched_lines.update(range(start_line, end_line + 1))
                line_nums[-1] = prev_start, end_line, matched_lines
                continue

        line_nums.append((start_line, end_line, set(range(start_line, end_line + 1))))

    return line_nums
