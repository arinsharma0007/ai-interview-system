from django import forms
from .models import Question , Candidate

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'subject', 'source_type', 'selected']

class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['name' , 'subject' , 'interview_type' , 'duration_minutes']