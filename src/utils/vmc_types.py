from typing import Union, List, Dict

Json = Union[List['Json'],
             Dict[str, 'Json'],
             str,
             float,
             bool,
             None]

