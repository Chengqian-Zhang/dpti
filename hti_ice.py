#!/usr/bin/env python3

import os, sys, json, argparse, glob, shutil
import numpy as np
import scipy.constants as pc

import einstein
import hti
import lib.lmp as lmp

def _main ():
    parser = argparse.ArgumentParser(
        description="Compute free energy by Hamiltonian TI")
    subparsers = parser.add_subparsers(title='Valid subcommands', dest='command')

    parser_gen = subparsers.add_parser('gen', help='Generate a job')
    parser_gen.add_argument('PARAM', type=str ,
                            help='json parameter file')
    parser_gen.add_argument('-f','--frenkel', action = 'store_true',
                            help='use Frenkel\'s Einstein crystal approach: remove COM')
    parser_gen.add_argument('-o','--output', type=str, default = 'new_job',
                            help='the output folder for the job')

    parser_comp = subparsers.add_parser('compute', help= 'Compute the result of a job')
    parser_comp.add_argument('JOB', type=str ,
                             help='folder of the job')
    parser_comp.add_argument('-t','--type', type=str, default = 'helmholtz', 
                             choices=['helmholtz', 'gibbs'], 
                             help='the type of free energy')
    parser_comp.add_argument('-m','--inte-method', type=str, default = 'inte', 
                             choices=['inte', 'mbar'], 
                             help='the method of thermodynamic integration')
    parser_comp.add_argument('-d','--disorder-corr', action = 'store_true',
                             help='apply disorder correction for ice')

    parser_comp = subparsers.add_parser('refine', help= 'Refine the grid of a job')
    parser_comp.add_argument('-i', '--input', type=str, required=True,
                             help='input job')
    parser_comp.add_argument('-o', '--output', type=str, required=True,
                             help='output job')
    parser_comp.add_argument('-e', '--error', type=float, required=True,
                             help='the error required')
    args = parser.parse_args()

    if args.command is None :
        parser.print_help()
        exit
    if args.command == 'gen' :
        output = args.output
        jdata = json.load(open(args.PARAM, 'r'))
        if args.frenkel :
            print('# gen task with Frenkel\'s Einstein crystal')
            hti.make_tasks(output, jdata, 'einstein', 'both', crystal = 'frenkel')
        else :
            print('# gen task with Vega\'s Einstein molecule')
            hti.make_tasks(output, jdata, 'einstein', 'both', crystal = 'vega')
    elif args.command == 'refine' :
        hti.refine_task(args.input, args.output, args.error)        
    elif args.command == 'compute' :
        job = args.JOB
        jdata = json.load(open(os.path.join(job, 'in.json'), 'r'))
        fp_conf = open(os.path.join(args.JOB, 'conf.lmp'))
        sys_data = lmp.to_system_data(fp_conf.read().split('\n'))
        natoms = sum(sys_data['atom_numbs'])
        if 'copies' in jdata :
            natoms *= np.prod(jdata['copies'])
        nmols = natoms // 3
        if 'reference' not in jdata :
            jdata['reference'] = 'einstein'
        if jdata['reference'] == 'einstein' :
            # e0 normalized by natoms, *3 to nmols
            e0 = einstein.free_energy(job) * 3
        else :
            raise RuntimeError("hti_ice should be used with reference einstein")
        if args.disorder_corr :
            temp = jdata['temp']
            pauling_corr = -pc.Boltzmann * temp / pc.electron_volt * np.log(1.5)            
            e0 += pauling_corr
        else :
            pauling_corr = 0
        if args.inte_method == 'inte' :
            de, de_err, thermo_info = hti.post_tasks(job, jdata, natoms = nmols)
        elif args.inte_method == 'mbar':
            de, de_err, thermo_info = hti.post_tasks_mbar(job, jdata, natoms = nmols)
        else :
            raise RuntimeError('unknow method for integration')        
        # printing
        print_format = '%20.12f  %10.3e  %10.3e'
        hti.print_thermo_info(thermo_info)
        print('# free ener of Einstein Mole: %20.8f' % (e0))
        print('# Pauling corr:               %20.8f' % (pauling_corr))
        print(('# fe integration              ' + print_format) \
              % (de, de_err[0], de_err[1]))        
        if args.type == 'helmholtz' :
            print('# Helmholtz free ener per mol (stat_err inte_err) [eV]:')
            print(print_format % (e0 + de, de_err[0], de_err[1]))
        if args.type == 'gibbs' :
            pv = thermo_info['pv']
            pv_err = thermo_info['pv_err']
            e1 = e0 + de + pv
            e1_err = np.sqrt(de_err[0]**2 + pv_err**2)
            print('# Gibbs free ener per mol (stat_err inte_err) [eV]:')
            print(print_format % (e1, e1_err, de_err[1]))


if __name__ == '__main__' :
    _main()
