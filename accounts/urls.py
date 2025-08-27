from django.urls import path
from . import views



urlpatterns = [
    path('', views.index, name='index'),
    path('accounts/register/', views.register_view, name='register'),
    path('accounts/login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Interviewer & Results path
    path("interviewer/",views.interviewer_view, name = "interviewer" ),
    path('interviewer/results/', views.result_list_view, name='result_list_view'),
    path('interviewer/results/<int:candidate_id>/', views.result_detail_view, name='result_detail_view'),
    path('add-candidate/', views.add_candidate_view, name='add_candidate'),


    # Questions CRUD
     path('questions/', views.question_list, name='question_list'),
     path('questions/create/', views.question_create, name='question_create'),
    path('questions/<int:pk>/edit/', views.question_edit, name='question_edit'),
    path('questions/<int:pk>/delete/', views.question_delete, name='question_delete'),
    path('questions/<int:pk>/toggle_selected/', views.toggle_selected, name='toggle_selected'),


     # Candidates CRUD
     path('candidates/' , views.candidate_list , name = "candidate_list"),
     path('candidates/create/' , views.candidate_create , name = "candidate_create"),
     path('candidate/<int:pk>/edit/' , views.candidate_edit , name = "candidate_edit"),
     path('candidate/<int:pk>/delete/' , views.candidate_delete , name = "candidate_delete"),

    # Manual
    path("manual_questions/", views.manual_questions_view, name="manual_questions"), # For addition of manual question

    # AI
    
     path('ai-questions/', views.ai_prompt_view, name='ai_prompt'),
     path('ai-questions/generate/', views.generate_ai_questions, name='generate_ai_questions'),
     path('interviewee/<int:candidate_id>/question/<int:question_id>/', views.interviewee_question_view, name='interviewee_question_view'),
     path("interviewee/<int:candidate_id>/start/", views.interview_start_view, name="interview_start_view"),
     path('interviewee/thank-you/', views.thank_you_view, name='thank_you'),


    # Assign 
     path("assign/select-candidate/", views.select_candidate_for_assignment, name="select_candidate_for_assignment"),
     path("assign/<int:candidate_id>/questions/", views.assign_questions_to_candidate, name="assign_questions"),
     path("assign/<int:candidate_id>/link/" , views.generate_interview_link , name = "generate_interview_link"),





    
     
     
]

     



