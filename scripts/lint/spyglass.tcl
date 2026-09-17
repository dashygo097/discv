foreach variable {FILELIST RTL_TOP BUILD_DIR} {
  if {![info exists ::env($variable)] || $::env($variable) eq ""} {
    error "required environment variable is not set: $variable"
  }
}

set_option enableSV yes
set_option top $::env(RTL_TOP)
read_file -type sourcelist $::env(FILELIST)
