from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.utils import timezone
from django.urls import reverse
from django.db.models import Exists, OuterRef
import os, logging, re
from datetime import datetime, timedelta
import google.generativeai as genai
from asgiref.sync import sync_to_async
from .models import Candidate, Question, Answer
from .forms import QuestionForm, CandidateForm

logger = logging.getLogger(__name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-2.5-pro")

# Helpers to wrap blocking calls
a_get_object = lambda model, **kw: sync_to_async(get_object_or_404)(model, **kw)
a_filter_list = lambda qs, **kw: sync_to_async(list)(qs.filter(**kw))
a_exists = lambda qs: sync_to_async(qs.exists)()
a_create = lambda model, **kw: sync_to_async(model.objects.create)(**kw)
a_save = lambda obj: sync_to_async(obj.save)()
a_delete = lambda obj: sync_to_async(obj.delete)()
a_auth = lambda req, **kw: sync_to_async(authenticate)(req, **kw)
a_login = lambda req, user: sync_to_async(login)(req, user)
a_logout = lambda req: sync_to_async(logout)(req)

# --- AUTH ---
async def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        if await a_exists(User.objects.filter(username=username)):
            return render(request, 'accounts/register.html', {'error': 'Username already exists'})
        user = await sync_to_async(User.objects.create_user)(username=username, password=password)
        await a_save(user)
        return redirect('login')
    return render(request, 'accounts/register.html')

async def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        next_url = request.GET.get('next')
        user = await a_auth(request, username=username, password=password)
        if user:
            await a_login(request, user)
            return redirect(next_url or 'index')
        return render(request, 'accounts/login.html', {'error': 'Invalid credentials'})
    return render(request, 'accounts/login.html')

async def logout_view(request):
    await a_logout(request)
    return redirect('login')

async def index(request):
    return render(request, 'accounts/index.html')

# --- INTERVIEW FLOW ---
async def interview_start_view(request, candidate_id):
    candidate = await a_get_object(Candidate, pk=candidate_id)
    if request.method == "POST":
        end_time = datetime.now() + timedelta(minutes=candidate.duration_minutes)
        await sync_to_async(request.session.__setitem__)("interview_end_time", end_time.isoformat())
        
        first_question = await sync_to_async(lambda: Question.objects.filter(candidate=candidate).first())()
        return redirect("interviewee_question_view", candidate_id=candidate.candidate_id, question_id=first_question.id)
    return render(request, "accounts/interviewee/start_interview.html", {"candidate": candidate})

async def select_candidate_for_assignment(request):
    candidates = await sync_to_async(list)(Candidate.objects.all())
    return render(request, "accounts/assign/select_candidate.html", {"candidates": candidates})

async def assign_questions_to_candidate(request, candidate_id):
    candidate = await a_get_object(Candidate, candidate_id=candidate_id)
    normalized_subject = candidate.subject.strip()
    questions = await a_filter_list(Question.objects, subject__iexact=normalized_subject, selected=True)
    if request.method == "POST":
        selected_ids = request.POST.getlist("questions")
        await sync_to_async(candidate.assigned_questions.set)(selected_ids)
        return redirect("generate_interview_link", candidate_id=candidate.candidate_id)
    return render(request, "accounts/assign/assign_questions.html", {"candidate": candidate, "questions": questions})

async def generate_interview_link(request, candidate_id):
    candidate = await a_get_object(Candidate, candidate_id=candidate_id)
    first_question = await sync_to_async(lambda: candidate.assigned_questions.order_by('id').first())()
    if not first_question:
        return HttpResponse("No questions assigned.")
    interview_url = request.build_absolute_uri(reverse("interview_start_view", args=[candidate.candidate_id]))
    return render(request, "accounts/assign/interview_link.html", {"link": interview_url, "candidate": candidate})

# Candidate helper
async def add_candidate(request):
    name = request.POST.get("name")
    subject = request.POST.get("subject")
    interview_type = request.POST.get("interview_type")
    duration_minutes = request.POST.get("duration_minutes")
    if not all([name, subject, interview_type]):
        return None, "All fields are required."
    candidate = await a_create(Candidate, name=name, subject=subject,
                               registration_date=timezone.now(),
                               interview_type=interview_type,
                               duration_minutes=duration_minutes)
    request.session['candidate_id'] = candidate.candidate_id
    return candidate, None

@login_required
async def add_candidate_view(request):
    candidate, error = None, None
    if request.method == "POST":
        candidate, error = await add_candidate(request)
        if not error:
            return render(request, "accounts/candidates/add_candidate.html", {"candidate": candidate})
    return render(request, "accounts/candidates/add_candidate.html", {"error": error})

@login_required
async def interviewer_view(request):
    candidate, error = None, None
    if request.method == "POST":
        candidate, error = await add_candidate(request)
        if error:
            return render(request, "accounts/interviewer.html", {"error": error})
    return render(request, "accounts/interviewer.html", {"candidate": candidate})

async def ai_prompt_view(request):
    if request.method == "POST":
        prompt = request.POST.get("prompt")
        if prompt:
            request.session["prompt"] = prompt
            return redirect("interviewee_ai")
    return render(request, "accounts/questions/ai_prompt.html")

# Clean/filter functions remain synchronous (fast CPU only)
def is_valid_question(text): ...
def clean_question(text): ...

import logging
logger = logging.getLogger(__name__)

async def generate_ai_questions(request):
    if request.method == "POST":
        # prompt = request.POST.get("prompt", "").strip()
        prompt = "List 5 HTML interview questions."  # Hardcoded for testing
        subject = request.POST.get("subject", "")
        logger.info(f"Prompt sent to Gemini: {prompt!r}")
        if not prompt:
            return render(request, "accounts/questions/ai_prompt.html", {"error": "Please enter a prompt."})
        try:
            response = await sync_to_async(model.generate_content)(prompt)
            logger.info(f"Gemini raw response: {response!r}")
            text = ""
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content"):
                    content = candidate.content
                    parts = getattr(content, "parts", None)
                    if parts and len(parts) > 0 and hasattr(parts[0], "text"):
                        text = parts[0].text
            if not text:
                logger.warning(f"Gemini response had no text: {response!r}")
                # Fallback for debugging
                text = "What is HTML?\nWhat does <a> tag do?\nHow do you add an image?\nWhat is a div?\nWhat is the difference between <ul> and <ol>?"
            raw_lines = [line.strip(" -*") for line in text.split("\n") if line.strip()]
            cleaned = [l for l in raw_lines if "?" in l]
            logger.info(f"Cleaned questions: {cleaned!r}")
        except Exception as e:
            return render(request, "accounts/questions/ai_prompt.html", {"error": f"Error generating questions: {e}"})
        if not cleaned:
            return render(request, "accounts/questions/ai_prompt.html", {"error": "No valid questions generated."})
        for q in cleaned:
            await a_create(Question, text=q, subject=subject, source_type="AI")
        return redirect("question_list")
    return redirect("ai_prompt")

async def interviewee_question_view(request, candidate_id, question_id):
    candidate = await a_get_object(Candidate, pk=candidate_id)
    question = await a_get_object(Question, pk=question_id)
    end_time_str = await sync_to_async(request.session.get)("interview_end_time")
    if not end_time_str:
        return redirect("interview_start_view", candidate_id=candidate_id)
    remaining_seconds = int((datetime.fromisoformat(end_time_str) - datetime.now()).total_seconds())
    if remaining_seconds <= 0:
        return redirect("thank_you")
    existing_answer = await sync_to_async(lambda: Answer.objects.filter(candidate=candidate, question=question).first())()
    selected_ids = await sync_to_async(list)(Question.objects.filter(selected=True, subject=candidate.subject).order_by("id").values_list("id", flat=True))
    try:
        current_index = selected_ids.index(question.id)
        next_id = selected_ids[current_index + 1]
    except (ValueError, IndexError):
        next_id = None
    if existing_answer:
        return render(request, "accounts/interviewee/interviewee_question.html",
                      {"question": question, "already_submitted": True,
                       "submitted_text": existing_answer.response,
                       "next_question_id": next_id, "remaining_seconds": remaining_seconds,
                       "candidate_id": candidate.candidate_id})
    if request.method == "POST":
        response_text = request.POST.get("response")
        if not response_text:
            return render(request, "interviewee/question.html",
                          {"question": question, "error": "Response cannot be empty.",
                           "remaining_seconds": remaining_seconds})
        await a_create(Answer, candidate=candidate, question=question, response=response_text)
        return redirect("interviewee_question_view", candidate_id=candidate_id, question_id=next_id) if next_id else redirect("thank_you")
    return render(request, "accounts/interviewee/interviewee_question.html",
                  {"question": question, "remaining_seconds": remaining_seconds})

async def thank_you_view(request):
    return render(request, 'accounts/thank_you.html')

@login_required
async def interview_result_view(request, candidate_id):
    candidate = await a_get_object(Candidate, candidate_id=candidate_id)
    answers = await a_filter_list(Answer.objects, candidate=candidate)
    return render(request, 'accounts/answer/evaluation.html', {'candidate': candidate, 'answers': answers})

@login_required
async def manual_questions_view(request):
    if request.method == "POST":
        text, subject = request.POST.get("question"), request.POST.get("subject")
        if text and subject:
            await a_create(Question, text=text, subject=subject)
        return redirect("manual_questions")
    questions = await sync_to_async(list)(Question.objects.all())
    return render(request, "accounts/manual/manual_questions.html", {"questions": questions})

async def result_list_view(request):
    candidates = await sync_to_async(lambda: list(
        Candidate.objects.annotate(
            has_answer=Exists(Answer.objects.filter(candidate=OuterRef('pk')))
        ).filter(has_answer=True)
    ))()
    return render(request, 'accounts/results/result_list.html', {'candidates': candidates})

def get_sentiment(feedback_text): ...

async def result_detail_view(request, candidate_id):
    candidate = await a_get_object(Candidate, pk=candidate_id)
    assigned_questions = await sync_to_async(list)(candidate.assigned_questions.all())
    evaluated = []
    for q in assigned_questions:
        answer = await sync_to_async(lambda: Answer.objects.filter(candidate=candidate, question=q).first())()
        if answer:
            if not answer.ai_feedback:
                feedback = await sync_to_async(evaluate_answer_with_ai)(q.text, answer.response)
                answer.ai_feedback = feedback
                await a_save(answer)
            evaluated.append({'question': q.text, 'answer': answer.response,
                              'ai_feedback': answer.ai_feedback,
                              'feedback_class': get_sentiment(answer.ai_feedback)})
        else:
            evaluated.append({'question': q.text, 'answer': None,
                              'ai_feedback': "❌ No answer provided.",
                              'feedback_class': "text-danger"})
    if request.method == "POST":
        verdict = request.POST.get("verdict")
        candidate.verdict = verdict
        await a_save(candidate)
        return redirect('result_list_view')
    return render(request, 'accounts/results/result_detail.html',
                  {'candidate': candidate, 'evaluated_answers': evaluated})

def evaluate_answer_with_ai(question, answer):
    prompt = f"..."
    response = model.generate_content(prompt)
    return response.text.strip()

# --- CRUD for Questions/Candidates ---
async def question_list(request):
    questions = await sync_to_async(list)(Question.objects.all().order_by('-created_at'))
    return render(request, 'accounts/questions/list.html', {'questions': questions})

async def question_create(request):
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            await sync_to_async(form.save)()
            return redirect('question_list')
    else:
        form = QuestionForm()
    return render(request, 'accounts/questions/form.html', {'form': form, 'title': 'Add Question'})

async def question_edit(request, pk):
    question = await a_get_object(Question, pk=pk)
    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            await sync_to_async(form.save)()
            return redirect('question_list')
    else:
        form = QuestionForm(instance=question)
    return render(request, 'accounts/questions/form.html', {'form': form, 'title': 'Edit Question'})

async def question_delete(request, pk):
    question = await a_get_object(Question, pk=pk)
    await a_delete(question)
    return redirect('question_list')

async def toggle_selected(request, pk):
    question = await a_get_object(Question, pk=pk)
    question.selected = not question.selected
    await a_save(question)
    return redirect('question_list')

async def candidate_list(request):
    candidates = await sync_to_async(list)(Candidate.objects.all().order_by('registration_date'))
    return render(request, "accounts/candidates/list.html", {'candidates': candidates})

async def candidate_create(request):
    if request.method == "POST":
        form = CandidateForm(request.POST)
        if form.is_valid():
            await sync_to_async(form.save)()
            return redirect('candidate_list')
    else:
        form = CandidateForm()
    return render(request, "accounts/candidates/form.html", {"form": form})

async def candidate_edit(request, pk):
    candidate = await a_get_object(Candidate, pk=pk)
    if request.method == "POST":
        form = CandidateForm(request.POST, instance=candidate)
        if form.is_valid():
            await sync_to_async(form.save)()
            return redirect('candidate_list')
    else:
        form = CandidateForm(instance=candidate)
    return render(request, "accounts/candidates/form.html", {"form": form})

async def candidate_delete(request, pk):
    candidate = await a_get_object(Candidate, pk=pk)
    if request.method == "POST":
        await a_delete(candidate)
        return redirect('candidate_list')
    return render(request, "accounts/candidates/confirm_delete.html", {"candidate": candidate})
