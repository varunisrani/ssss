from typing import Optional, Dict, Any, Union
from services.db_service import db_service

async def find_next_best_element_position(canvas_data, max_num_per_row=4):

    elements = canvas_data.get("elements", [])

    # 查找最后一个图片或视频元素（同时考虑两种类型）
    last_x: Union[int, float] = 0
    last_y: Union[int, float] = 0
    last_width: Union[int, float] = 0
    last_height: Union[int, float] = 0
    
    # 同时考虑图片和视频元素，确保不重叠
    media_elements = [
        element for element in elements 
        if element.get("type") in ["image", "embeddable", "video"]
    ]

    # Sort elements by updated timestamp to find the most recently created element
    media_elements.sort(key=lambda e: e.get("updated", 0))

    last_media_element = media_elements[-1] if len(media_elements) > 0 else None

    if last_media_element is not None:
        last_x = last_media_element.get("x", 0)
        last_y = last_media_element.get("y", 0)
        last_width = last_media_element.get("width", 0)
        last_height = last_media_element.get("height", 0)
        
        # 判断同一y坐标上是否已有max_num_per_row个组件
        same_y_elements = [
            element for element in media_elements 
            if element.get("y", 0) == last_y
        ]
        
        # 如果同一y坐标上已有max_num_per_row个组件，则换行
        if len(same_y_elements) >= max_num_per_row:
            new_x = 0  # 换行后从x=0开始
            new_y = last_y + last_height + 20  # 换行，y坐标增加高度加间距
        else:
            new_x = last_x + last_width + 20
            new_y = last_y
    else:
        new_x = 0
        new_y = 0

    return new_x, new_y