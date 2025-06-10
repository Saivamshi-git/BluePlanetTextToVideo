from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from .utils.mongo import get_collection
from .utils.mongo import get_db
from .utils.mongo import get_gridfs_bucket
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from django.http import HttpResponse
import base64


@api_view(['GET'])
def get_audio_by_batch(request, batch_id):
    script_collection = get_collection("text_to_video_db", "scripts")
    doc = script_collection.find_one({"batch_id": batch_id})

    if not doc or "audio_base64" not in doc:
        return Response({"error": "Audio not found"}, status=404)

    audio_bytes = base64.b64decode(doc["audio_base64"])
    response = HttpResponse(audio_bytes, content_type=doc.get("content_type", "audio/mpeg"))
    response["Content-Disposition"] = f'inline; filename="{doc.get("filename", "audio.mp3")}"'
    return response



@api_view(['POST']) 
@parser_classes([MultiPartParser])
def save_script(request):
    script_text = request.POST.get("script")
    batch_id = request.POST.get("batch_id")
    label = request.POST.get("label")
    part_number = request.POST.get("part_number")
    percentage = request.POST.get("percentage")
    audio_file = request.FILES.get("audio")

    # Basic validation
    if not all([script_text, batch_id, label, part_number, percentage, audio_file]):
        return Response({"error": "Missing required data"}, status=400)

    try:
        audio_file.seek(0)
        audio_binary = audio_file.read()

        if not audio_binary:
            return Response({"error": "Uploaded audio file is empty"}, status=400)

        audio_base64 = base64.b64encode(audio_binary).decode('utf-8')

        script_collection = get_collection("text_to_video_db", "scripts")

        # Save each part as a unique doc: one per (batch_id, part_number)
        script_collection.update_one(
            {"batch_id": batch_id, "part_number": int(part_number)},
            {
                "$set": {
                    "label": label,
                    "script": script_text,
                    "percentage": float(percentage),
                    "audio_base64": audio_base64,
                    "filename": audio_file.name,
                    "content_type": audio_file.content_type
                }
            },
            upsert=True
        )

        return Response({"status": "✅ Script and audio saved for part", "part": part_number})

    except Exception as e:
        return Response({"error": f"Failed to save audio in DB: {str(e)}"}, status=500)


@api_view(['GET'])
def get_image(request, file_id):
    fs = get_gridfs_bucket()
    try:
        image = fs.get(ObjectId(file_id))
        return HttpResponse(image.read(), content_type=image.content_type)
    except:
        return Response({"error": "Image not found"}, status=404)
    

@api_view(['DELETE'])
def delete_batch(request, batch_id):
    fs = get_gridfs_bucket()
    db = get_db("text_to_video_db")

    # Delete all GridFS files
    for file in fs.find({"metadata.batch_id": batch_id}):
        fs.delete(file._id)

    # Delete batch record
    db["batches"].delete_one({"batch_id": batch_id})

    db["scripts"].delete_one({"batch_id": batch_id})


    return Response({"status": "deleted", "batch_id": batch_id})

@api_view(['GET'])
def list_images_by_batch(request, batch_id):
    fs = get_gridfs_bucket()
    files = list(fs.find({"metadata.batch_id": batch_id}))
    image_list = [
        {
            "filename": f.filename,
            "file_id": str(f._id)
        }
        for f in files
    ]

    return Response(image_list)  # ✅ returns a list, not a dict




@api_view(['POST'])
def cleanup_inactive_batches(request):
    db = get_db("text_to_video_db")
    fs = get_gridfs_bucket()
    cutoff = datetime.utcnow() - timedelta(minutes=5) #minutes=5 #hours=1

    inactive_batches = list(db["batches"].find({"last_active": {"$lt": cutoff}}))
    deleted_batches = []

    for batch in inactive_batches:
        batch_id = batch["batch_id"]

        # Delete all files with this batch_id
        for file in fs.find({"metadata.batch_id": batch_id}):
            fs.delete(file._id)

        db["scripts"].delete_one({"batch_id": batch_id})

        # Delete the batch record itself
        db["batches"].delete_one({"batch_id": batch_id})
        deleted_batches.append(batch_id)

    return Response({
        "status": "cleanup complete",
        "deleted_batches": deleted_batches,
        "count": len(deleted_batches)
    })


@api_view(['POST'])
@parser_classes([MultiPartParser])
def upload_folder(request):
    image_file = request.FILES.get("image")
    batch_id = request.POST.get("batch_id")

    if not image_file or not batch_id:
        return Response({"error": "Missing required data"}, status=400)

    # Save image to GridFS
    fs = get_gridfs_bucket()
    file_id = fs.put(
        image_file,
        filename=image_file.name,
        content_type=image_file.content_type,
        metadata={
            "batch_id": batch_id,
            "upload_time": datetime.utcnow()
        }
    )

    # ✅ Update or insert batch record
    collection = get_collection("text_to_video_db","batches")
    collection.update_one(
        {"batch_id": batch_id},
        {
            "$set": {"last_active": datetime.utcnow()},
            "$setOnInsert": {"created_at": datetime.utcnow()}
        },
        upsert=True
    )

    return Response({
        "status": "image saved",
        "file_id": str(file_id),
        "filename": image_file.name,
        "batch_id": batch_id
    })

@api_view(['GET'])
def test_api(request):
    return Response({"message": "API is working ✅"})