# DC-specific settings are interpreted here, not by the build driver.
proc project_dc_get {table key fallback} {
  if {[dict exists $table $key]} { return [dict get $table $key] }
  return $fallback
}

proc project_dc_paths {paths} {
  set result {}
  foreach path $paths {
    lappend result [file normalize [file join $::env(PROJECT_ROOT) $path]]
  }
  return $result
}

proc project_dc_config {project} {
  if {![dict exists $project technology dc target_libraries]} {
    error "selected technology requires dc.target_libraries"
  }
  set tech [dict get $project technology dc]
  set flow [dict get $project flow]
  set target [project_dc_paths [dict get $tech target_libraries]]
  if {[llength $target] == 0} { error "dc.target_libraries must not be empty" }
  set link [project_dc_paths [project_dc_get $tech link_libraries {}]]
  set pairs {}
  foreach pair [project_dc_get $tech library_pairs {}] {
    set maximum [lindex [project_dc_paths [list [dict get $pair max]]] 0]
    set minimum [lindex [project_dc_paths [list [dict get $pair min]]] 0]
    if {[lsearch -exact [concat $target $link] $maximum] < 0} {
      error "library_pairs.max must reference a target or link library: $maximum"
    }
    lappend pairs [list $maximum $minimum]
  }
  set compile [project_dc_get $flow compile ultra]
  if {$compile ni {ultra standard}} { error "compile must be ultra or standard" }
  foreach key {preserve_hierarchy retime clock_gating} {
    set value [project_dc_get $flow $key [expr {$key eq "preserve_hierarchy"}]]
    if {![string is boolean -strict $value]} { error "$key must be boolean" }
    set $key $value
  }
  if {$retime && $compile ne "ultra"} { error "retime requires compile = ultra" }
  return [dict create \
    RTL_TOP [dict get $project architecture top] \
    SYNTH_TARGET_LIBRARIES $target SYNTH_LINK_LIBRARIES $link \
    SYNTH_SYNTHETIC_LIBRARIES [project_dc_paths [project_dc_get $tech synthetic_libraries {}]] \
    SYNTH_MIN_LIBRARY_PAIRS $pairs \
    SYNTH_SETUP_SCRIPTS [project_dc_paths [project_dc_get $tech setup_scripts {}]] \
    SYNTH_COMPILE $compile SYNTH_PRESERVE_HIERARCHY $preserve_hierarchy \
    SYNTH_RETIME $retime SYNTH_CLOCK_GATING $clock_gating]
}

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
    BENDER_SCRIPT
    CONSTRAINTS_SDC
    STAGE_CONFIG
    STAGE_WORK_DIR
    STAGE_REPORT_DIR
    STAGE_RESULT_DIR
    BUILD_JOBS
    RTL_TOP
  }

  source $::env(STAGE_CONFIG)
  set dc_config [project_dc_config $PROJECT]
  dict with dc_config {}

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

  foreach script $SYNTH_SETUP_SCRIPTS {
    project_require_file $script "technology setup script"
    uplevel #0 [list source $script]
  }
  # Bender reads and updates DC application variables in the global scope.
  if {[uplevel #0 [list source $::env(BENDER_SCRIPT)]] eq "1"} {
    error "Bender-generated HDL analysis failed"
  }

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

  uplevel #0 [list source $::env(CONSTRAINTS_SDC)]

  set check_timing_ok true
  redirect -file [file join $report_dir check_timing.pre.rpt] {
    set check_timing_ok [check_timing]
  }
  if {!$check_timing_ok} {
    error "check_timing failed before compilation"
  }

  if {$SYNTH_COMPILE eq "ultra"} {
    set compile_command [list compile_ultra]
    if {$SYNTH_PRESERVE_HIERARCHY} {
      lappend compile_command -no_autoungroup
    }
    if {$SYNTH_RETIME} {
      lappend compile_command -retime
    }
    if {$SYNTH_CLOCK_GATING} {
      lappend compile_command -gate_clock
    }
    eval $compile_command
  } elseif {$SYNTH_COMPILE eq "standard"} {
    if {$SYNTH_RETIME} {
      error "retime requires compile = ultra"
    }
    set compile_command [list compile]
    if {$SYNTH_CLOCK_GATING} {
      lappend compile_command -gate_clock
    }
    eval $compile_command
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

set project_status [catch {project_main} project_error project_options]
if {$project_status != 0} {
  puts stderr "ERROR: $project_error"
  puts stderr [dict get $project_options -errorinfo]
  exit 1
}
exit 0
