from django import forms

class SendMessageForm(forms.Form):
    send_to = forms.CharField(min_length=1)
    subject = forms.CharField()
    body = forms.CharField()
