from django.urls import path
from .views import test_api, save_script,upload_folder,cleanup_inactive_batches,delete_batch,list_images_by_batch, get_image,get_audio_by_batch

urlpatterns = [
    path('test/', test_api),
    path('save-script/', save_script),
    path('upload-folder/', upload_folder),
    path('cleanup-inactive-batches/', cleanup_inactive_batches),
    path('delete-batch/<str:batch_id>/', delete_batch),
    path('list-images/<str:batch_id>/', list_images_by_batch),
    path('get-image/<str:file_id>/', get_image),
    path('get-audio/<str:batch_id>/', get_audio_by_batch),


]
