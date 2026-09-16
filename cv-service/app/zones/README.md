# Zones extension point

Phase 7 monitoring-zone math is implemented in the backend's spatial services,
which consume persisted tracking frames. This keeps one canonical implementation
and avoids repeated YOLO/ByteTrack inference when zones change after upload.
See [spatial analysis](../../../docs/spatial-analysis.md).
