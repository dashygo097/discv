foreach variable {RTL_FILELIST RTL_TOP STAGE_WORK_DIR} {
  if {![info exists ::env($variable)] || $::env($variable) eq ""} {
    error "required environment variable is not set: $variable"
  }
}

set_option enableSV09 yes
set_option top $::env(RTL_TOP)
set_option projectwdir $::env(STAGE_WORK_DIR)
read_file -type sourcelist $::env(RTL_FILELIST)

if {[info exists ::SPYGLASS_HOME]} {
  set spyglass_home $::SPYGLASS_HOME
} elseif {[info exists ::env(SPYGLASS_HOME)]} {
  set spyglass_home $::env(SPYGLASS_HOME)
} else {
  error "SpyGlass installation directory is unavailable"
}
current_methodology [file join $spyglass_home GuideWare latest block rtl_handoff]
unset spyglass_home
