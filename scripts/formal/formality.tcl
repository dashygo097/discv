proc project_main {} {
  foreach name {BENDER_SCRIPT STAGE_CONFIG STAGE_REPORT_DIR DEPENDENCY_RESULTS RTL_TOP} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {
      error "missing environment variable: $name"
    }
  }
  source $::env(STAGE_CONFIG)
  set SYNTH_TARGET_LIBRARIES [dict get $PROJECT technology dc target_libraries]
  set SYNTH_LINK_LIBRARIES {}
  if {[dict exists $PROJECT technology dc link_libraries]} {
    set SYNTH_LINK_LIBRARIES [dict get $PROJECT technology dc link_libraries]
  }
  set libraries {}
  foreach path [concat $SYNTH_TARGET_LIBRARIES $SYNTH_LINK_LIBRARIES] {
    lappend libraries [file normalize [file join $::env(PROJECT_ROOT) $path]]
  }
  set top $::env(RTL_TOP)
  set netlist [file join $::env(DEPENDENCY_RESULTS) ${top}.v]
  set guidance [file join $::env(DEPENDENCY_RESULTS) ${top}.svf]
  foreach path [concat [list $netlist $guidance] $libraries] {
    if {![file isfile $path]} {
      error "missing equivalence input: $path"
    }
  }
  set_app_var sh_continue_on_error false
  set ::synopsys_auto_setup true
  set_svf $guidance
  if {[uplevel #0 [list source $::env(BENDER_SCRIPT)]] eq "1"} {
    error "Bender-generated reference read failed"
  }
  if {![set_top r:/WORK/$top]} {
    error "failed to elaborate reference: $top"
  }
  foreach library $libraries {
    read_db -i $library
  }
  read_verilog -i -libname WORK -netlist $netlist
  if {![set_top i:/WORK/$top]} {
    error "failed to link implementation: $top"
  }
  set reports $::env(STAGE_REPORT_DIR)
  redirect -file [file join $reports setup.rpt] { report_setup_status }
  match
  set passed [verify]
  redirect -file [file join $reports summary.rpt] { report_verification_status }
  redirect -file [file join $reports matched.rpt] { report_matched_points }
  redirect -file [file join $reports unmatched.rpt] { report_unmatched_points }
  redirect -file [file join $reports failing.rpt] { report_failing_points }
  redirect -file [file join $reports aborted.rpt] { report_aborted_points }
  if {!$passed} {
    error "RTL-to-gate equivalence verification failed"
  }
}
if {[catch {project_main} message options]} {
  puts stderr "ERROR: $message"
  puts stderr [dict get $options -errorinfo]
  exit 1
}
exit 0
