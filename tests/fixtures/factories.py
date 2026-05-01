from domain import Borehole


def make_borehole(name: str, root_path: str, section_name: str = "section-1", step_number: int = 1) -> Borehole:
    borehole = Borehole(name, root_path)
    borehole.add_section(section_name, depth_=10, length_=5.5)
    section = borehole.section_list[0]
    section.add_step(step_number)
    return borehole
