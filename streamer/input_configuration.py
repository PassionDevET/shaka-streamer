# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import enum
import platform
import shlex

from . import bitrate_configuration
from . import configuration


class InputType(enum.Enum):
  FILE = 'file'
  """A track from a file.  Usable only with VOD."""

  LOOPED_FILE = 'looped_file'
  """A track from a file, looped forever by FFmpeg.  Usable only with live.

  Does not support media_type of 'text'.
  """

  WEBCAM = 'webcam'
  """A webcam device.  Usable only with live.

  The device path should be given in the name field.  For example, on Linux,
  this might be /dev/video0.

  Does not support media_type of 'text'.
  """

  RAW_IMAGES = 'raw_images'
  """A file or pipe with a sequence of raw images.

  Requires the specification of frame_rate.  May require the use of
  extra_input_args if FFmpeg can't guess the format.

  Does not support media_type of 'text' or 'audio'.
  """

  EXTERNAL_COMMAND = 'external_command'
  """An external command that generates a stream of audio or video.

  The command should be given in the name field, using shell quoting rules.
  The command should send its generated output to the path in the environment
  variable $SHAKA_STREAMER_EXTERNAL_COMMAND_OUTPUT, which Shaka Streamer set to
  the path to the output pipe.

  May require the user of extra_input_args if FFmpeg can't guess the format or
  framerate.

  Does not support media_type of 'text'.
  """

class MediaType(enum.Enum):
  AUDIO = 'audio'
  VIDEO = 'video'
  TEXT = 'text'


class Input(configuration.Base):
  """An object representing a single input stream to Shaka Streamer."""

  input_type = configuration.Field(InputType, default=InputType.FILE)
  """The type of the input."""

  name = configuration.Field(str, required=True)
  """Name of the input.

  With input_type set to 'file', this is a path to a file name.

  With input_type set to 'looped_file', this is a path to a file name to be
  looped indefinitely in FFmpeg.

  With input_type set to 'webcam', this is a path to the device node for the
  webcam.  For example, on Linux, this might be /dev/video0.

  With input_type set to 'raw_images', this is a path to a file or pipe
  containing a sequence of raw images.

  With input_type set to 'external_command', this is an external command that
  generates a stream of audio or video.  The command will be parsed using shell
  quoting rules.  The command should send its generated output to the path in
  the environment variable $SHAKA_STREAMER_EXTERNAL_COMMAND_OUTPUT, which Shaka
  Streamer set to the path to the output pipe.
  """

  extra_input_args = configuration.Field(str, default='')
  """Extra input arguments needed by FFmpeg to understand the input.

  This allows you to take inputs that cannot be understand or detected
  automatically by FFmpeg.

  This string will be parsed using shell quoting rules.
  """

  media_type = configuration.Field(MediaType, required=True)
  """The media type of the input stream."""

  frame_rate = configuration.Field(float)
  """The frame rate of the input stream, in frames per second.

  Only valid for media_type of 'video'.

  Can be auto-detected for some input types, but may be required for others.
  For example, required for input_type of 'external_command'.
  """

  resolution = configuration.Field(bitrate_configuration.Resolution)
  """The name of the input resolution (1080p, etc).

  Only valid for media_type of 'video'.

  Can be auto-detected for some input types, but may be required for others.
  For example, required for input_type of 'external_command'.
  """

  track_num = configuration.Field(int, default=0)
  """The track number of the input.

  The track number is specific to the media_type.  For example, if there is one
  video track and two audio tracks, media_type of 'audio' and track_num of '0'
  indicates the first audio track, not the first track overall in that file.

  If unspecified, track_num will default to 0, meaning the first track matching
  the media_type field will be used.
  """

  is_interlaced = configuration.Field(bool)
  """True if the input video is interlaced.

  Only valid for media_type of 'video'.

  If true, the video will be deinterlaced during transcoding.

  Can be auto-detected for some input types, but may be default to False for
  others.  For example, an input_type of 'external_command', it will default to
  False.
  """

  language = configuration.Field(str)
  """The language of an audio or text stream.

  With input_type set to 'file' or 'looped_file', this will be auto-detected.
  Otherwise, it will default to 'und' (undetermined).
  """

  start_time = configuration.Field(str)
  """The start time of the slice of the input to use.

  Only valid for VOD and with input_type set to 'file'.

  Not supported with media_type of 'text'.
  """

  end_time = configuration.Field(str)
  """The end time of the slice of the input to use.

  Only valid for VOD and with input_type set to 'file'.

  Not supported with media_type of 'text'.
  """

  filters = configuration.Field(list, subtype=str, default=[])
  """A list of FFmpeg filter strings to add to the transcoding of this input.

  Each filter is a single string.  For example, 'pad=1280:720:20:20'.

  Not supported with media_type of 'text'.
  """


  def __init__(self, *args):
    super().__init__(*args)

    # FIXME: A late import to avoid circular dependency issues between these two
    # modules.
    from . import autodetect

    def require_field(name):
      """Raise MissingRequiredField if the named field is still missing."""
      if getattr(self, name) is None:
        raise configuration.MissingRequiredField(
            self.__class__, name, getattr(self.__class__, name))

    def disallow_field(name, reason):
      """Raise MalformedField if the named field is present."""
      if getattr(self, name):
        raise configuration.MalformedField(
            self.__class__, name, getattr(self.__class__, name), reason)

    if self.media_type == MediaType.VIDEO:
      # These fields are required for video inputs.
      # We will attempt to auto-detect them if possible.
      if self.is_interlaced is None:
        self.is_interlaced = autodetect.get_interlaced(self)

      if self.frame_rate is None:
        self.frame_rate = autodetect.get_frame_rate(self)
      require_field('frame_rate')

      if self.resolution is None:
        self.resolution = autodetect.get_resolution(self)
      require_field('resolution')

    if self.media_type == MediaType.AUDIO or self.media_type == MediaType.TEXT:
      # Language is required for audio and text inputs.
      # We will attempt to auto-detect this.
      if self.language is None:
        self.language = autodetect.get_language(self) or 'und'

    if self.media_type == MediaType.TEXT:
      # Text streams are only supported in plain file inputs.
      if self.input_type != InputType.FILE:
        reason = 'text streams are not supported in input_type "{}"'.format(
            self.input_type.value)
        disallow_field('input_type', reason)

      # These fields are not supported with text, because we don't process or
      # transcode it.
      reason = 'not supported with media_type "text"'
      disallow_field('start_time', reason)
      disallow_field('end_time', reason)
      disallow_field('filters', reason)

    if self.input_type == InputType.RAW_IMAGES:
      if self.media_type != MediaType.VIDEO:
        reason = 'input_type "raw_images" only supports media_type "video"'
        disallow_field('media_type', reason)

    if self.input_type != InputType.FILE:
      # These fields are only valid for file inputs.
      reason = 'only valid when input_type is "file"'
      disallow_field('start_time', reason)
      disallow_field('end_time', reason)

    # This needs to be parsed into an argument array.  Note that shlex.split on
    # an empty string will produce an empty array.
    self.extra_input_args = shlex.split(self.extra_input_args)

    # A path to a pipe into which this input's contents are fed.
    # None for most input types.
    self._pipe = None

  def set_pipe(self, pipe):
    """Set the path to a pipe into which this input's contents are fed.

    If set, this is what TranscoderNode will read from instead of .name.
    """

    self._pipe = pipe

  def get_path_for_transcode(self):
    """Get the path which the transcoder will use to read the input.

    For some input types, this is a named pipe.  For others, this is .name.
    """

    return self._pipe or self.name

  def get_stream_specifier(self):
    """Get an FFmpeg stream specifier for this input.

    For example, the first video track would be "v:0", and the 3rd text track
    would be "s:2".  Note that all track numbers are per media type in this
    format, not overall track numbers from the input file, and that they are
    indexed starting at 0.

    See also http://ffmpeg.org/ffmpeg.html#Stream-specifiers
    """

    if self.media_type == MediaType.VIDEO:
      return 'v:{}'.format(self.track_num)
    elif self.media_type == MediaType.AUDIO:
      return 'a:{}'.format(self.track_num)
    elif self.media_type == MediaType.TEXT:
      return 's:{}'.format(self.track_num)

    assert False, 'Unrecognized media_type!  This should not happen.'

  def get_input_args(self):
    """Get any required input arguments for this input.

    These are like hard-coded extra_input_args for certain input types.
    This means users don't have to know much about FFmpeg options to handle
    these common cases.

    Note that for types which support autodetect, these arguments must be
    understood by ffprobe as well as ffmpeg.
    """
    if self.input_type == InputType.RAW_IMAGES:
      return [
          # Parse the input as a stream of images fed into a pipe.
          '-f', 'image2pipe',
          # Set the frame rate to the one specified in the input config.
          # Note that this is the input framerate for the image2 dexuxer, which
          # is not what the similar '-r' option is meant for.
          '-framerate', str(input.frame_rate),
      ]
    elif self.input_type == InputType.WEBCAM:
      if platform.system() == 'Linux':
        return [
            # Treat the input as a video4linux device, which is how webcams show
            # up on Linux.
            '-f', 'video4linux2',
        ]
      else:
        assert False, 'Webcams not supported on this platform!'

    return []


class InputConfig(configuration.Base):
  """An object representing the entire input config to Shaka Streamer."""

  inputs = configuration.Field(list, subtype=Input, required=True)
  """A list of Input objects, one per input stream."""

