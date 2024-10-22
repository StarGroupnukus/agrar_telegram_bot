from pydantic import BaseModel, Field
from typing import List

class Student(BaseModel):
    id: int
    name: str
    hemis_id: int

class Faculty(BaseModel):
    id: int
    faculty: str

class Group(BaseModel):
    id: int
    name: str

class StudentDetail(BaseModel):
    id: int
    name: str
    hemis_id: int
    faculty: Group
    group: Group

class AbsentGroup(BaseModel):
    group_id: int
    group_name: str
    total_students: int
    absent_students_count: int
    absent_students: List[Student]

class Pagination(BaseModel):
    total: int
    current_page: int
    last_page: int
    per_page: int
    total_pages: int = Field(..., alias="total_pages")

class NoteComersResponse(BaseModel):
    success: bool
    pagination: Pagination
    data: list[AbsentGroup]

class AllStudentsResponse(BaseModel):
    success: bool
    pagination: Pagination
    data: list[StudentDetail]

class FacultyResponse(BaseModel):
    success: bool
    total: int
    data: list[Faculty]

class StudentChat(BaseModel):
    student_id: int
    chat_id: int
