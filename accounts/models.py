from django.db import models
from django.utils import timezone

# Create your models here.
class Question(models.Model):
    text = models.TextField()
    subject = models.CharField(max_length=255)
    source_type = models.CharField(max_length=10, choices=[('Manual', 'Manual'), ('AI', 'AI')] ,default='Manual')
    created_at = models.DateTimeField(auto_now_add=True)
    selected = models.BooleanField(default=False)
   
    

def __str__(self):
        return f"{self.subject}: {self.text[:50]}"




class Candidate(models.Model):
    candidate_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    registration_date = models.DateTimeField(auto_now_add=True)
    subject = models.CharField(max_length=255)
    verdict = models.CharField(max_length=20 , null=True , blank=True),
    INTERVIEW_TYPE_CHOICES = [
        ("AI" , "AI-Based Interview"),
        ("Manual" , "Manual Interview")
    ]

    interview_type = models.CharField(
        max_length=10,
        choices= INTERVIEW_TYPE_CHOICES,
        default="Manual",
        
    )
    assigned_questions = models.ManyToManyField(Question, blank=True)
    duration_minutes = models.IntegerField(default=60)
    


    def __str__(self):
        return f"{self.name} {self.subject} ({self.candidate_id}) ({self.interview_type})"
    
class Answer(models.Model):
         candidate = models.ForeignKey(Candidate , on_delete=models.CASCADE)
         question = models.ForeignKey(Question , on_delete=models.CASCADE)
         response = models.TextField()
         EVALUATION_CHOICES = [
         ("correct", "Correct"),
         ("incorrect", "Incorrect"),
         ("pending", "Pending"),]

         evaluation = models.CharField(
            max_length=20,
            choices=EVALUATION_CHOICES,
            default="pending"
)       
         created_at = models.DateTimeField(auto_now_add=True)
         ai_feedback = models.TextField(null=True, blank=True)




class Meta:
    unique_together = ('candidate', 'question')