from typing import Union, List, Dict

JSON = Union[List['JSON'],
             Dict[str, 'JSON'],
             str,
             float,
             bool,
             None]

