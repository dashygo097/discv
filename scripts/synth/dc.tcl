proc project_require_environment {names} {
  foreach name $names {
    if {![info exists ::env($name)] || $::env($name) eq ""} {
      error "required environment variable is not set: $name"
    }
  }
}

proc project_require_file {path description} {
  if {![file isfile $path]} {
    error "$description does not exist: $path"
  }
}

proc project_main {} {
  project_require_environment {
    RTL_TCL
    CONSTRAINTS_SDC
    SYNTH_DC_CONFIG
    STAGE_WORK_DIR
    STAGE_REPORT_DIR
    STAGE_RESULT_DIR
    BUILD_JOBS
    RTL_TOP
  }

  source $::env(RTL_TCL)
  source $::env(SYNTH_DC_CONFIG)

  if {$RTL_TOP ne $::env(RTL_TOP)} {
    error "generated RTL top does not match the stage environment"
  }
  if {[llength $SYNTH_TARGET_LIBRARIES] == 0} {
    error "no Design Compiler target library is configured"
  }

  foreach library [concat \
      $SYNTH_TARGET_LIBRARIES \
      $SYNTH_LINK_LIBRARIES \
      $SYNTH_SYNTHETIC_LIBRARIES] {
    project_require_file $library "synthesis library"
  }
  foreach pair $SYNTH_MIN_LIBRARY_PAIRS {
    project_require_file [lindex $pair 0] "maximum-delay library"
    project_require_file [lindex $pair 1] "minimum-delay library"
  }

  set work_dir $::env(STAGE_WORK_DIR)
  set report_dir $::env(STAGE_REPORT_DIR)
  set result_dir $::env(STAGE_RESULT_DIR)
  set design_lib_dir [file join $work_dir design_lib]
  file mkdir $design_lib_dir

  set library_search_paths {}
  foreach library [concat \
      $SYNTH_TARGET_LIBRARIES \
      $SYNTH_LINK_LIBRARIES \
      $SYNTH_SYNTHETIC_LIBRARIES] {
    lappend library_search_paths [file dirname $library]
  }

  set_app_var sh_continue_on_error false
  set_app_var search_path [concat \
      [get_app_var search_path] \
      $RTL_INCLUDE_DIRS \
      $library_search_paths]
  set_app_var target_library $SYNTH_TARGET_LIBRARIES
  set_app_var link_library [concat \
      [list *] \
      $SYNTH_TARGET_LIBRARIES \
      $SYNTH_LINK_LIBRARIES \
      $SYNTH_SYNTHETIC_LIBRARIES]
  if {[llength $SYNTH_SYNTHETIC_LIBRARIES] > 0} {
    set_app_var synthetic_library $SYNTH_SYNTHETIC_LIBRARIES
  }

  foreach pair $SYNTH_MIN_LIBRARY_PAIRS {
    set_min_library [lindex $pair 0] -min_version [lindex $pair 1]
  }

  set_host_options -max_cores $::env(BUILD_JOBS)
  define_design_lib WORK -path $design_lib_dir
  set_svf [file join $result_dir ${RTL_TOP}.svf]

  set analyze_command [list analyze -format sverilog -library WORK]
  if {[llength $RTL_DEFINES] > 0} {
    lappend analyze_command -define $RTL_DEFINES
  }
  lappend analyze_command $RTL_SOURCES
  eval $analyze_command

  elaborate $RTL_TOP -library WORK
  current_design $RTL_TOP
  if {![link]} {
    error "failed to link design: $RTL_TOP"
  }

  set check_design_ok true
  redirect -file [file join $report_dir check_design.pre.rpt] {
    set check_design_ok [check_design]
  }
  if {!$check_design_ok} {
    error "check_design failed before compilation"
  }

  source $::env(CONSTRAINTS_SDC)

  set check_timing_ok true
  redirect -file [file join $report_dir check_timing.pre.rpt] {
    set check_timing_ok [check_timing]
  }
  if {!$check_timing_ok} {
    error "check_timing failed before compilation"
  }

  if {$SYNTH_COMPILE eq "ultra"} {
    compile_ultra -no_autoungroup
  } elseif {$SYNTH_COMPILE eq "standard"} {
    compile
  } else {
    error "unsupported compilation mode: $SYNTH_COMPILE"
  }

  set check_design_ok true
  redirect -file [file join $report_dir check_design.rpt] {
    set check_design_ok [check_design]
  }
  if {!$check_design_ok} {
    error "check_design failed after compilation"
  }

  set check_timing_ok true
  redirect -file [file join $report_dir check_timing.rpt] {
    set check_timing_ok [check_timing]
  }
  if {!$check_timing_ok} {
    error "check_timing failed after compilation"
  }

  redirect -file [file join $report_dir summary.rpt] { report_qor }
  redirect -file [file join $report_dir qor.rpt] { report_qor }
  redirect -file [file join $report_dir area.rpt] { report_area -hierarchy }
  redirect -file [file join $report_dir timing.setup.rpt] {
    report_timing -delay_type max -max_paths 50 \
        -transition_time -nets -attributes
  }
  redirect -file [file join $report_dir timing.hold.rpt] {
    report_timing -delay_type min -max_paths 50 \
        -transition_time -nets -attributes
  }
  redirect -file [file join $report_dir constraints.rpt] {
    report_constraint -all_violators
  }
  redirect -file [file join $report_dir power.rpt] { report_power }

  write -format ddc -hierarchy -output [file join $result_dir ${RTL_TOP}.ddc]
  write_file -format verilog -hierarchy -output [file join $result_dir ${RTL_TOP}.v]
  write_sdc [file join $result_dir ${RTL_TOP}.sdc]
  set_svf -off
}

set project_status [catch {project_main} project_error]
if {$project_status != 0} {
  puts stderr "ERROR: $project_error"
  exit 1
}
exit 0
